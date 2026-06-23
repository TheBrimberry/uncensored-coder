//+------------------------------------------------------------------+
//|                                  OmniscientTradingAgent.mq5       |
//|     MQL5 port of the Omniscient Trading Agent's tradeable core.   |
//|                                                                   |
//|  Multi-strategy ensemble + regime filter + ATR risk management.   |
//|  Account guardian: risk-based sizing, mandatory SL/TP,            |
//|  daily-loss circuit breaker, and total-drawdown kill switch.      |
//|                                                                   |
//|  Honest by design: this is a disciplined rules engine, not a      |
//|  money printer. Test on a DEMO account first. No guarantees.      |
//+------------------------------------------------------------------+
#property copyright "Omniscient Trading Agent"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//====================================================================
//  INPUTS
//====================================================================
input group "=== Risk Guardian ==="
input double InpRiskPct          = 1.0;    // Risk % of equity per trade
input double InpMaxDailyLossPct  = 5.0;    // Daily loss % -> halt for the day
input double InpMaxDrawdownPct   = 20.0;   // Total drawdown % -> kill switch
input int    InpMaxOpenPositions = 1;      // Max simultaneous positions (this EA)
input double InpAtrStopMult      = 2.0;    // Stop-loss = ATR * this
input double InpRewardRisk       = 2.0;    // Take-profit = stop distance * this

input group "=== Signal / Ensemble ==="
input double InpSignalThreshold  = 0.20;   // |net bias| needed to trade (0..1)
input bool   InpUseRegimeFilter  = true;   // Skip trades in dangerous regimes

input group "=== Indicator Periods ==="
input int    InpEmaFast          = 20;     // Fast EMA
input int    InpEmaSlow          = 50;     // Slow EMA
input int    InpRsiPeriod        = 14;     // RSI period
input int    InpBbPeriod         = 20;     // Bollinger period
input double InpBbDev            = 2.0;    // Bollinger deviations
input int    InpAtrPeriod        = 14;     // ATR period
input int    InpAdxPeriod        = 14;     // ADX period
input int    InpStochK           = 14;     // Stochastic %K
input int    InpStochD           = 3;      // Stochastic %D
input int    InpDonchianPeriod   = 20;     // Donchian breakout lookback

input group "=== General ==="
input long   InpMagic            = 990011;  // Magic number (EA id)
input int    InpSlippagePoints   = 20;      // Max slippage (points)
input bool   InpTradeOncePerBar  = true;    // One decision per new bar

//====================================================================
//  GLOBALS
//====================================================================
CTrade   trade;

int      hEmaFast, hEmaSlow, hRsi, hMacd, hBands, hAtr, hAdx, hStoch;

datetime g_lastBarTime   = 0;
double   g_peakEquity    = 0.0;     // all-time-high equity since EA start
double   g_dayStartEquity= 0.0;     // equity at start of current server day
int      g_currentDay    = -1;
bool     g_killSwitch    = false;   // permanent halt after max drawdown

//+------------------------------------------------------------------+
//| Helper: create an indicator handle and verify it                  |
//+------------------------------------------------------------------+
bool ValidHandle(const int handle, const string name)
{
   if(handle == INVALID_HANDLE)
   {
      Print("Failed to create indicator handle: ", name);
      return(false);
   }
   return(true);
}

//+------------------------------------------------------------------+
//| OnInit                                                            |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   hEmaFast = iMA(_Symbol, _Period, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hEmaSlow = iMA(_Symbol, _Period, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hRsi     = iRSI(_Symbol, _Period, InpRsiPeriod, PRICE_CLOSE);
   hMacd    = iMACD(_Symbol, _Period, 12, 26, 9, PRICE_CLOSE);
   hBands   = iBands(_Symbol, _Period, InpBbPeriod, 0, InpBbDev, PRICE_CLOSE);
   hAtr     = iATR(_Symbol, _Period, InpAtrPeriod);
   hAdx     = iADX(_Symbol, _Period, InpAdxPeriod);
   hStoch   = iStochastic(_Symbol, _Period, InpStochK, InpStochD, 3,
                          MODE_SMA, STO_LOWHIGH);

   if(!ValidHandle(hEmaFast,"EMAfast") || !ValidHandle(hEmaSlow,"EMAslow") ||
      !ValidHandle(hRsi,"RSI")        || !ValidHandle(hMacd,"MACD")       ||
      !ValidHandle(hBands,"Bands")    || !ValidHandle(hAtr,"ATR")         ||
      !ValidHandle(hAdx,"ADX")        || !ValidHandle(hStoch,"Stoch"))
      return(INIT_FAILED);

   g_peakEquity     = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEquity = g_peakEquity;

   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   g_currentDay = dt.day;

   Print("Omniscient Trading Agent EA initialized on ", _Symbol,
         " | risk ", InpRiskPct, "% | RR ", InpRewardRisk);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| OnDeinit                                                          |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(hEmaFast); IndicatorRelease(hEmaSlow);
   IndicatorRelease(hRsi);     IndicatorRelease(hMacd);
   IndicatorRelease(hBands);   IndicatorRelease(hAtr);
   IndicatorRelease(hAdx);     IndicatorRelease(hStoch);
}

//+------------------------------------------------------------------+
//| Read the most recent value of an indicator buffer                 |
//+------------------------------------------------------------------+
bool ReadBuf(const int handle, const int buffer, const int shift, double &out)
{
   double tmp[];
   if(CopyBuffer(handle, buffer, shift, 1, tmp) < 1)
      return(false);
   out = tmp[0];
   return(true);
}

//+------------------------------------------------------------------+
//| Count positions opened by THIS EA on THIS symbol                  |
//+------------------------------------------------------------------+
int CountMyPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC)  == InpMagic)
         n++;
   }
   return(n);
}

//+------------------------------------------------------------------+
//| ENSEMBLE: combine strategy votes into a net bias in [-1, +1]      |
//|   +1 = strong long, -1 = strong short                             |
//+------------------------------------------------------------------+
double EnsembleBias()
{
   double score  = 0.0;   // signed, strength-weighted
   double weight = 0.0;   // total strength

   double emaF, emaS, rsi, macdMain, macdSig, bbU, bbL, price;
   double kNow, kPrev, dNow, dPrev, adx, plusDI, minusDI;

   price = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   // --- 1. EMA crossover (trend) ---
   if(ReadBuf(hEmaFast,0,0,emaF) && ReadBuf(hEmaSlow,0,0,emaS) && emaS!=0)
   {
      double spread = MathAbs(emaF - emaS) / emaS;
      double str    = MathMin(spread * 20.0, 1.0);
      if(emaF > emaS) { score += str; }
      else            { score -= str; }
      weight += str;
   }

   // --- 2. RSI mean-reversion ---
   if(ReadBuf(hRsi,0,0,rsi))
   {
      if(rsi < 30)      { double s=MathMin((30-rsi)/30.0,1.0); score += s; weight += s; }
      else if(rsi > 70) { double s=MathMin((rsi-70)/30.0,1.0); score -= s; weight += s; }
   }

   // --- 3. MACD momentum (histogram sign & slope) ---
   double mNow, mPrev, sNow, sPrev;
   if(ReadBuf(hMacd,0,0,mNow) && ReadBuf(hMacd,1,0,sNow) &&
      ReadBuf(hMacd,0,1,mPrev)&& ReadBuf(hMacd,1,1,sPrev))
   {
      double histNow  = mNow  - sNow;
      double histPrev = mPrev - sPrev;
      bool rising = histNow > histPrev;
      if(histNow > 0 && rising)       { score += 0.6; weight += 0.6; }
      else if(histNow < 0 && !rising) { score -= 0.6; weight += 0.6; }
   }

   // --- 4. Bollinger breakout (volatility expansion) ---
   if(ReadBuf(hBands,1,0,bbU) && ReadBuf(hBands,2,0,bbL))
   {
      if(price > bbU)      { score += 0.6; weight += 0.6; }
      else if(price < bbL) { score -= 0.6; weight += 0.6; }
   }

   // --- 5. Stochastic cross from extremes ---
   if(ReadBuf(hStoch,0,0,kNow) && ReadBuf(hStoch,1,0,dNow) &&
      ReadBuf(hStoch,0,1,kPrev)&& ReadBuf(hStoch,1,1,dPrev))
   {
      if(kNow > dNow && kPrev <= dPrev && kNow < 80) { score += 0.5; weight += 0.5; }
      if(kNow < dNow && kPrev >= dPrev && kNow > 20) { score -= 0.5; weight += 0.5; }
   }

   // --- 6. ADX trend-strength with DI direction ---
   if(ReadBuf(hAdx,0,0,adx) && ReadBuf(hAdx,1,0,plusDI) && ReadBuf(hAdx,2,0,minusDI))
   {
      if(adx >= 25)
      {
         double s = MathMin((adx - 25) / 25.0, 1.0);
         if(plusDI > minusDI) { score += s; }
         else                 { score -= s; }
         weight += s;
      }
   }

   // --- 7. Donchian breakout (Turtle) ---
   double hh = -DBL_MAX, ll = DBL_MAX;
   double highs[], lows[];
   if(CopyHigh(_Symbol,_Period,1,InpDonchianPeriod,highs) == InpDonchianPeriod &&
      CopyLow (_Symbol,_Period,1,InpDonchianPeriod,lows ) == InpDonchianPeriod)
   {
      for(int i=0;i<InpDonchianPeriod;i++)
      {
         if(highs[i] > hh) hh = highs[i];
         if(lows[i]  < ll) ll = lows[i];
      }
      if(price >= hh)      { score += 0.65; weight += 0.65; }
      else if(price <= ll) { score -= 0.65; weight += 0.65; }
   }

   if(weight <= 0.0) return(0.0);
   return(score / weight);   // normalized net bias
}

//+------------------------------------------------------------------+
//| REGIME: returns a size factor (0 = don't trade, >0 = scale)       |
//+------------------------------------------------------------------+
double RegimeSizeFactor()
{
   double atr, adx, price;
   if(!ReadBuf(hAtr,0,0,atr)) return(1.0);
   if(!ReadBuf(hAdx,0,0,adx)) adx = 0.0;
   price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(price <= 0) return(1.0);

   double atrPct = atr / price * 100.0;

   // High-volatility regime: ATR% very elevated -> half size
   if(atrPct > 4.0) return(0.5);
   // Strong trend -> slightly larger
   if(adx > 40)     return(1.25);
   // Trending -> full
   if(adx >= 25)    return(1.0);
   // Ranging -> slightly smaller (breakouts whipsaw)
   return(0.8);
}

//+------------------------------------------------------------------+
//| Position size from risk %, SL distance, broker constraints        |
//+------------------------------------------------------------------+
double LotByRisk(const double slDistancePrice, const double sizeFactor)
{
   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney  = equity * (InpRiskPct/100.0) * sizeFactor;

   double tickValue  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickValue <= 0 || slDistancePrice <= 0) return(0.0);

   double moneyPerLot = (slDistancePrice / tickSize) * tickValue;
   if(moneyPerLot <= 0) return(0.0);

   double lot = riskMoney / moneyPerLot;

   // Normalize to broker volume step / min / max
   double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(volStep > 0) lot = MathFloor(lot / volStep) * volStep;
   lot = MathMax(lot, volMin);
   lot = MathMin(lot, volMax);
   return(lot);
}

//+------------------------------------------------------------------+
//| GUARDIAN: returns true if trading is ALLOWED right now            |
//+------------------------------------------------------------------+
bool GuardianAllowsTrading()
{
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);

   // Track all-time peak equity for drawdown
   if(equity > g_peakEquity) g_peakEquity = equity;

   // New server day? reset the daily anchor
   MqlDateTime dt; TimeToStruct(TimeCurrent(), dt);
   if(dt.day != g_currentDay)
   {
      g_currentDay     = dt.day;
      g_dayStartEquity = equity;
   }

   // Permanent kill switch (max total drawdown)
   if(g_killSwitch) return(false);
   if(g_peakEquity > 0)
   {
      double ddPct = (g_peakEquity - equity) / g_peakEquity * 100.0;
      if(ddPct >= InpMaxDrawdownPct)
      {
         g_killSwitch = true;
         Print("KILL SWITCH: total drawdown ", DoubleToString(ddPct,2),
               "% >= ", InpMaxDrawdownPct, "%. Trading halted permanently.");
         return(false);
      }
   }

   // Daily loss circuit breaker (resets next day)
   if(g_dayStartEquity > 0)
   {
      double dayLossPct = (g_dayStartEquity - equity) / g_dayStartEquity * 100.0;
      if(dayLossPct >= InpMaxDailyLossPct)
         return(false);   // halted for today
   }

   // Position cap
   if(CountMyPositions() >= InpMaxOpenPositions)
      return(false);

   return(true);
}

//+------------------------------------------------------------------+
//| OnTick                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   // Trade once per new bar if requested
   datetime barTime = (datetime)SeriesInfoInteger(_Symbol, _Period, SERIES_LASTBAR_DATE);
   if(InpTradeOncePerBar)
   {
      if(barTime == g_lastBarTime) return;
      g_lastBarTime = barTime;
   }

   if(!GuardianAllowsTrading()) return;

   // Regime gate
   double sizeFactor = 1.0;
   if(InpUseRegimeFilter)
   {
      sizeFactor = RegimeSizeFactor();
      if(sizeFactor <= 0.0) return;
   }

   double bias = EnsembleBias();
   if(MathAbs(bias) < InpSignalThreshold) return;   // no conviction

   // ATR-based stop & target distances
   double atr;
   if(!ReadBuf(hAtr,0,0,atr) || atr <= 0) return;
   double slDist = atr * InpAtrStopMult;
   double tpDist = slDist * InpRewardRisk;

   double lot = LotByRisk(slDist, sizeFactor);
   if(lot <= 0) return;

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   if(bias > 0)   // LONG — SL/TP always attached
   {
      double sl = NormalizeDouble(ask - slDist, digits);
      double tp = NormalizeDouble(ask + tpDist, digits);
      if(trade.Buy(lot, _Symbol, ask, sl, tp,
         "OmniAgent long bias=" + DoubleToString(bias,2)))
         Print("LONG ", lot, " @ ", ask, " SL ", sl, " TP ", tp,
               " bias ", DoubleToString(bias,2), " sizeF ", sizeFactor);
   }
   else           // SHORT
   {
      double sl = NormalizeDouble(bid + slDist, digits);
      double tp = NormalizeDouble(bid - tpDist, digits);
      if(trade.Sell(lot, _Symbol, bid, sl, tp,
         "OmniAgent short bias=" + DoubleToString(bias,2)))
         Print("SHORT ", lot, " @ ", bid, " SL ", sl, " TP ", tp,
               " bias ", DoubleToString(bias,2), " sizeF ", sizeFactor);
   }
}
//+------------------------------------------------------------------+
