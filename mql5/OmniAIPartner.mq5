//+------------------------------------------------------------------+
//|                                          OmniAIPartner.mq5        |
//|        Interactive AI Trading Partner for MetaTrader 5            |
//|                                                                   |
//|  The "hands and eyes" of the Omniscient Trading Agent. It works   |
//|  WITH you: protects every trade, manages exits, scans for the     |
//|  patterns you care about and alerts you, draws the key levels on  |
//|  your chart, tells you which strategy fits this symbol right now,  |
//|  trades the session open when you are away, and answers your       |
//|  questions by talking to the Python AI brain (Ollama) over a       |
//|  local link.                                                       |
//|                                                                   |
//|  Honest by design. TEST ON DEMO FIRST. No profit is guaranteed.   |
//+------------------------------------------------------------------+
#property copyright "Omniscient Trading Agent"
#property version   "2.00"
#property strict

#include <Trade/Trade.mqh>

//====================================================================
//  INPUTS
//====================================================================
input group "=== AI Brain Link (Python agent) ==="
input bool   InpEnableAI        = true;                        // Enable "Ask AI" chat
input string InpAIServerURL     = "http://127.0.0.1:8765";     // Python serve.py URL

input group "=== Auto-Protect (do what you forget) ==="
input bool   InpAutoProtect     = true;     // Attach SL/TP to naked positions
input bool   InpProtectManual   = true;     // Also protect trades you placed by hand
input double InpAtrStopMult     = 2.0;      // SL distance = ATR * this
input double InpRewardRisk      = 2.0;      // TP = SL distance * this

input group "=== Trade Management ==="
input bool   InpUseBreakeven    = true;     // Move SL to entry after a push in profit
input double InpBreakevenAtr     = 1.0;     // Profit (in ATR) before breakeven
input bool   InpUseTrailing     = true;     // ATR trailing stop
input double InpTrailAtr         = 2.0;     // Trail distance in ATR

input group "=== Pattern Scanner + Alerts ==="
input bool   InpScanPatterns    = true;     // Watch for patterns and alert
input string InpWatchPatterns   = "engulfing,hammer,star,doji,squeeze,breakout,divergence"; // which
input bool   InpPopupAlert      = true;     // On-screen popup alert
input bool   InpPushAlert       = false;    // Phone push (needs MetaQuotes ID set)
input bool   InpSoundAlert      = true;     // Play a sound

input group "=== Chart Drawing (key levels) ==="
input bool   InpDrawLevels      = true;     // Draw key lines on the chart
input bool   InpDrawPrevDay     = true;     // Prior-day high/low
input bool   InpDrawDonchian    = true;     // Range high/low (support/resistance)
input bool   InpDrawPivots      = true;     // Daily pivot + R1/S1
input bool   InpDrawRound       = true;     // Nearest round number

input group "=== Strategy Advisor ==="
input bool   InpAdvisorOnInit   = true;     // Run advisor when EA loads
input int    InpAdvisorBars     = 500;      // Bars of history to evaluate

input group "=== Proactive Signal Watch (watches your back) ==="
input bool   InpProactiveSignals = true;    // Auto-push high-value signals (no asking)
input double InpSignalMinConv     = 0.45;    // Min conviction (0..1) to push a signal
input bool   InpSignalAskAI       = false;   // Add a one-line AI rationale to each signal

input group "=== Session Timing (trade while you're away) ==="
input bool   InpAutoTradeSession= false;    // Auto-trade at session open
input int    InpSessionHour     = 8;        // Server hour of session open
input int    InpSessionMinute   = 0;        // Minute
input double InpSignalThreshold = 0.20;     // Net ensemble bias needed to trade

input group "=== Risk Guardian ==="
input double InpRiskPct         = 1.0;      // Risk % of equity per trade
input double InpMaxDailyLossPct = 5.0;      // Daily loss % -> halt for the day
input double InpMaxDrawdownPct  = 20.0;     // Total drawdown % -> kill switch
input int    InpMaxOpenPositions= 2;        // Max simultaneous EA positions
input int    InpMaxTradesPerDay = 5;        // Cap new trades per day
input double InpMaxSpreadPoints  = 0;        // Skip if spread above this (0=off)

input group "=== News Filter (economic calendar) ==="
input bool   InpNewsPause       = true;     // Pause trading around high-impact news
input int    InpNewsMinsBefore  = 30;       // Minutes before an event to pause
input int    InpNewsMinsAfter   = 15;       // Minutes after an event to stay paused
input bool   InpNewsHighOnly    = true;     // Only react to HIGH-impact events

input group "=== Multi-Symbol Scanner (watch a basket) ==="
input bool   InpMultiScan       = true;     // Scan a watchlist and alert the best move
input string InpWatchSymbols    = "EURUSD,GBPUSD,USDJPY,XAUUSD,US500"; // comma list
input double InpMultiMinConv    = 0.50;     // Min conviction to flag a watchlist symbol

input group "=== Dashboard / General ==="
input bool   InpShowDashboard   = true;     // On-chart risk dashboard
input long   InpMagic           = 990022;   // Magic number (EA id)
input int    InpSlippagePoints  = 20;       // Max slippage (points)
input int    InpPeriods         = 14;       // Base period for RSI/ATR/ADX

//====================================================================
//  GLOBALS
//====================================================================
CTrade   trade;
int      hEmaF, hEmaS, hEma200, hRsi, hMacd, hBands, hAtr, hAdx, hStoch;

datetime g_lastBar      = 0;
double   g_peakEquity   = 0.0;
double   g_dayStartEq   = 0.0;
int      g_currentDay   = -1;
int      g_tradesToday  = 0;
bool     g_kill         = false;
string   g_bestStrategy = "(not evaluated)";
string   g_lastAnswer   = "";
int      g_lastSignalDir= 0;        // -1/0/+1, to avoid spamming the same signal
bool     g_newsActive   = false;    // true while inside a news blackout window

// Multi-symbol scanner state
string   g_watch[];
int      g_watchCount   = 0;
int      g_wEmaF[], g_wEmaS[], g_wRsi[], g_wAdx[];
string   g_lastScanSym  = "";
int      g_lastScanDir  = 0;

string   UI_INPUT = "omni_input";
string   UI_ASK   = "omni_ask";
string   UI_ADV   = "omni_adv";

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   hEmaF   = iMA(_Symbol,_Period,20,0,MODE_EMA,PRICE_CLOSE);
   hEmaS   = iMA(_Symbol,_Period,50,0,MODE_EMA,PRICE_CLOSE);
   hEma200 = iMA(_Symbol,_Period,200,0,MODE_EMA,PRICE_CLOSE);
   hRsi    = iRSI(_Symbol,_Period,InpPeriods,PRICE_CLOSE);
   hMacd   = iMACD(_Symbol,_Period,12,26,9,PRICE_CLOSE);
   hBands  = iBands(_Symbol,_Period,20,0,2.0,PRICE_CLOSE);
   hAtr    = iATR(_Symbol,_Period,InpPeriods);
   hAdx    = iADX(_Symbol,_Period,InpPeriods);
   hStoch  = iStochastic(_Symbol,_Period,14,3,3,MODE_SMA,STO_LOWHIGH);

   if(hEmaF==INVALID_HANDLE || hEmaS==INVALID_HANDLE || hEma200==INVALID_HANDLE ||
      hRsi==INVALID_HANDLE  || hMacd==INVALID_HANDLE || hBands==INVALID_HANDLE ||
      hAtr==INVALID_HANDLE  || hAdx==INVALID_HANDLE  || hStoch==INVALID_HANDLE)
   {
      Print("Indicator handle creation failed."); return(INIT_FAILED);
   }

   g_peakEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = g_peakEquity;
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt); g_currentDay = dt.day;

   if(InpMultiScan) SetupWatchlist();
   if(InpEnableAI) CreateChatUI();
   if(InpAdvisorOnInit) g_bestStrategy = RunStrategyAdvisor(true);
   if(InpDrawLevels) DrawKeyLevels();

   Print("OmniAIPartner ready on ",_Symbol,". Best strategy: ",g_bestStrategy);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(hEmaF); IndicatorRelease(hEmaS); IndicatorRelease(hEma200);
   IndicatorRelease(hRsi);  IndicatorRelease(hMacd); IndicatorRelease(hBands);
   IndicatorRelease(hAtr);  IndicatorRelease(hAdx);  IndicatorRelease(hStoch);
   for(int i=0;i<g_watchCount;i++)
   {
      IndicatorRelease(g_wEmaF[i]); IndicatorRelease(g_wEmaS[i]);
      IndicatorRelease(g_wRsi[i]);  IndicatorRelease(g_wAdx[i]);
   }
   ObjectsDeleteAll(0,"omni_");
   Comment("");
}

//+------------------------------------------------------------------+
//| Read most-recent indicator value (shift 0 = current bar)          |
//+------------------------------------------------------------------+
bool RB(const int h,const int buf,const int shift,double &out)
{
   double t[]; if(CopyBuffer(h,buf,shift,1,t)<1) return(false); out=t[0]; return(true);
}

//+------------------------------------------------------------------+
void OnTick()
{
   GuardianUpdate();              // refresh equity/day/drawdown bookkeeping

   if(InpAutoProtect)  AutoProtectPositions();
   ManageOpenTrades();            // breakeven + trailing
   if(InpShowDashboard) UpdateDashboard();

   datetime bar = (datetime)SeriesInfoInteger(_Symbol,_Period,SERIES_LASTBAR_DATE);
   if(bar==g_lastBar) return;     // everything below runs once per new bar
   g_lastBar = bar;

   g_newsActive = (InpNewsPause) ? NewsBlackout() : false;

   if(InpDrawLevels)       DrawKeyLevels();
   if(InpScanPatterns)     ScanPatterns();
   if(InpProactiveSignals) ProactiveSignalWatch();
   if(InpMultiScan)        MultiSymbolScan();
   if(InpAutoTradeSession) SessionLogic();
}

//+------------------------------------------------------------------+
//| PROACTIVE SIGNAL WATCH                                            |
//|  Watches the market every bar and pushes a fully-formed, high-    |
//|  conviction trade idea (direction, entry, SL, TP, R:R, reasons)   |
//|  WITHOUT being asked. Debounced so it won't spam the same call.   |
//+------------------------------------------------------------------+
void ProactiveSignalWatch()
{
   double bias=EnsembleBias();
   double conv=MathAbs(bias);
   int dir=(bias>0)?1:(bias<0?-1:0);

   // Need conviction; only alert when the call is fresh (direction changed)
   if(conv<InpSignalMinConv || dir==0){ if(dir==0) g_lastSignalDir=0; return; }
   if(dir==g_lastSignalDir) return;          // already alerted this call
   g_lastSignalDir=dir;

   // Regime context + confluence reasons
   double atr,adx,rsi;
   if(!RB(hAtr,0,0,atr)||atr<=0) return;
   if(!RB(hAdx,0,0,adx)) adx=0;
   if(!RB(hRsi,0,0,rsi)) rsi=50;
   double sf=RegimeSizeFactor();
   string regime = (sf<=0.5)?"high-volatility (half size!)":
                   (adx>=25?"trending":"ranging");

   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double price=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double slDist=atr*InpAtrStopMult, tpDist=slDist*InpRewardRisk;
   double entry=price;
   double sl=(dir>0)?price-slDist:price+slDist;
   double tp=(dir>0)?price+tpDist:price-tpDist;
   double lot=LotByRisk(slDist,sf<=0?1.0:sf);

   string side=(dir>0)?"LONG":"SHORT";
   string newsTag=g_newsActive?"[NEWS WINDOW — caution] ":"";
   string msg=newsTag+StringFormat(
      "SIGNAL %s %s | conv %.0f%% | %s\n"
      "Entry ~%s  SL %s  TP %s  (R:R 1:%.1f)\n"
      "Suggested size %.2f lots @ %.1f%% risk  | RSI %.0f  ADX %.0f",
      side,_Symbol,conv*100.0,regime,
      DoubleToString(entry,digits),DoubleToString(sl,digits),
      DoubleToString(tp,digits),InpRewardRisk,
      lot,InpRiskPct,rsi,adx);

   Notify(msg);

   // Optional: enrich with a one-line AI rationale from the Python brain
   if(InpSignalAskAI && InpEnableAI)
   {
      string ai=AskAI("In one sentence, why might a "+side+
                      " on "+_Symbol+" make sense right now?");
      if(StringLen(ai)>0 && StringFind(ai,"Could not reach")<0)
         Comment("AI on latest signal:\n"+ai);
   }
}

//+------------------------------------------------------------------+
//| GUARDIAN bookkeeping + gate                                       |
//+------------------------------------------------------------------+
void GuardianUpdate()
{
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(eq>g_peakEquity) g_peakEquity = eq;
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt);
   if(dt.day!=g_currentDay){ g_currentDay=dt.day; g_dayStartEq=eq; g_tradesToday=0; }
   if(!g_kill && g_peakEquity>0)
   {
      double dd=(g_peakEquity-eq)/g_peakEquity*100.0;
      if(dd>=InpMaxDrawdownPct){ g_kill=true;
         Print("KILL SWITCH: drawdown ",DoubleToString(dd,2),"%. Halted."); }
   }
}

bool GuardianAllows()
{
   if(g_kill) return(false);
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   if(g_dayStartEq>0 && (g_dayStartEq-eq)/g_dayStartEq*100.0>=InpMaxDailyLossPct) return(false);
   if(g_tradesToday>=InpMaxTradesPerDay) return(false);
   if(CountMyPositions()>=InpMaxOpenPositions) return(false);
   if(InpMaxSpreadPoints>0)
   {
      double sp=(double)SymbolInfoInteger(_Symbol,SYMBOL_SPREAD);
      if(sp>InpMaxSpreadPoints) return(false);
   }
   return(true);
}

int CountMyPositions()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      if(PositionGetTicket(i)==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol &&
         PositionGetInteger(POSITION_MAGIC)==InpMagic) n++;
   }
   return(n);
}

//+------------------------------------------------------------------+
//| AUTO-PROTECT: attach SL/TP to any naked position                  |
//+------------------------------------------------------------------+
void AutoProtectPositions()
{
   double atr; if(!RB(hAtr,0,0,atr)||atr<=0) return;
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double slDist=atr*InpAtrStopMult, tpDist=slDist*InpRewardRisk;

   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      long magic=PositionGetInteger(POSITION_MAGIC);
      bool mine=(magic==InpMagic);
      if(!mine && !InpProtectManual) continue;

      double sl=PositionGetDouble(POSITION_SL);
      double tp=PositionGetDouble(POSITION_TP);
      if(sl>0 && tp>0) continue;                 // already protected

      long type=PositionGetInteger(POSITION_TYPE);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double newSL=sl, newTP=tp;
      if(type==POSITION_TYPE_BUY)
      {
         if(sl<=0) newSL=NormalizeDouble(open-slDist,digits);
         if(tp<=0) newTP=NormalizeDouble(open+tpDist,digits);
      }
      else
      {
         if(sl<=0) newSL=NormalizeDouble(open+slDist,digits);
         if(tp<=0) newTP=NormalizeDouble(open-tpDist,digits);
      }
      if(trade.PositionModify(tk,newSL,newTP))
         Print("Auto-protected ",(mine?"EA":"manual")," ticket ",tk,
               " SL ",newSL," TP ",newTP);
   }
}

//+------------------------------------------------------------------+
//| MANAGE: breakeven + ATR trailing for this EA's trades             |
//+------------------------------------------------------------------+
void ManageOpenTrades()
{
   if(!InpUseBreakeven && !InpUseTrailing) return;
   double atr; if(!RB(hAtr,0,0,atr)||atr<=0) return;
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;

      long type=PositionGetInteger(POSITION_TYPE);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl=PositionGetDouble(POSITION_SL);
      double tp=PositionGetDouble(POSITION_TP);
      double newSL=sl;

      if(type==POSITION_TYPE_BUY)
      {
         double profit=bid-open;
         if(InpUseBreakeven && profit>=InpBreakevenAtr*atr && (sl<open))
            newSL=NormalizeDouble(open,digits);
         if(InpUseTrailing)
         {
            double trail=NormalizeDouble(bid-InpTrailAtr*atr,digits);
            if(trail>newSL) newSL=trail;
         }
         if(newSL>sl && newSL<bid) trade.PositionModify(tk,newSL,tp);
      }
      else
      {
         double profit=open-ask;
         if(InpUseBreakeven && profit>=InpBreakevenAtr*atr && (sl>open||sl<=0))
            newSL=NormalizeDouble(open,digits);
         if(InpUseTrailing)
         {
            double trail=NormalizeDouble(ask+InpTrailAtr*atr,digits);
            if(trail<newSL||newSL<=0) newSL=trail;
         }
         if((newSL<sl||sl<=0) && newSL>ask) trade.PositionModify(tk,newSL,tp);
      }
   }
}

//+------------------------------------------------------------------+
//| ENSEMBLE bias in [-1,+1] (used by session auto-trade)             |
//+------------------------------------------------------------------+
double EnsembleBias()
{
   double score=0,weight=0,v,v2,price=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double emaF,emaS; if(RB(hEmaF,0,0,emaF)&&RB(hEmaS,0,0,emaS)&&emaS!=0)
   { double s=MathMin(MathAbs(emaF-emaS)/emaS*20.0,1.0);
     if(emaF>emaS) score+=s; else score-=s; weight+=s; }
   double rsi; if(RB(hRsi,0,0,rsi))
   { if(rsi<30){double s=MathMin((30-rsi)/30.0,1.0);score+=s;weight+=s;}
     else if(rsi>70){double s=MathMin((rsi-70)/30.0,1.0);score-=s;weight+=s;} }
   double mN,sN,mP,sP; if(RB(hMacd,0,0,mN)&&RB(hMacd,1,0,sN)&&RB(hMacd,0,1,mP)&&RB(hMacd,1,1,sP))
   { double hN=mN-sN,hP=mP-sP; if(hN>0&&hN>hP){score+=0.6;weight+=0.6;}
     else if(hN<0&&hN<hP){score-=0.6;weight+=0.6;} }
   double bu,bl; if(RB(hBands,1,0,bu)&&RB(hBands,2,0,bl))
   { if(price>bu){score+=0.6;weight+=0.6;} else if(price<bl){score-=0.6;weight+=0.6;} }
   double adx,pdi,ndi; if(RB(hAdx,0,0,adx)&&RB(hAdx,1,0,pdi)&&RB(hAdx,2,0,ndi))
   { if(adx>=25){double s=MathMin((adx-25)/25.0,1.0);
       if(pdi>ndi)score+=s; else score-=s; weight+=s;} }
   if(weight<=0) return(0);
   return(score/weight);
}

//+------------------------------------------------------------------+
//| REGIME size factor                                               |
//+------------------------------------------------------------------+
double RegimeSizeFactor()
{
   double atr,adx,price=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(!RB(hAtr,0,0,atr)||price<=0) return(1.0);
   if(!RB(hAdx,0,0,adx)) adx=0;
   double atrPct=atr/price*100.0;
   if(atrPct>4.0) return(0.5);
   if(adx>40) return(1.25);
   if(adx>=25) return(1.0);
   return(0.8);
}

//+------------------------------------------------------------------+
double LotByRisk(const double slDist,const double sizeFactor)
{
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double riskMoney=eq*(InpRiskPct/100.0)*sizeFactor;
   double tv=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
   double ts=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
   if(ts<=0||tv<=0||slDist<=0) return(0);
   double perLot=(slDist/ts)*tv; if(perLot<=0) return(0);
   double lot=riskMoney/perLot;
   double vmin=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double vmax=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   double vstep=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   if(vstep>0) lot=MathFloor(lot/vstep)*vstep;
   lot=MathMax(lot,vmin); lot=MathMin(lot,vmax);
   return(lot);
}

//+------------------------------------------------------------------+
//| SESSION: at the configured open time, trade the ensemble bias     |
//+------------------------------------------------------------------+
void SessionLogic()
{
   MqlDateTime dt; TimeToStruct(TimeCurrent(),dt);
   if(dt.hour!=InpSessionHour || dt.min<InpSessionMinute || dt.min>InpSessionMinute+5) return;
   if(g_newsActive){ Print("Session trade skipped — news blackout active."); return; }
   if(!GuardianAllows()) return;
   double bias=EnsembleBias();
   if(MathAbs(bias)<InpSignalThreshold) return;
   double sf=RegimeSizeFactor(); if(sf<=0) return;
   double atr; if(!RB(hAtr,0,0,atr)||atr<=0) return;
   double slDist=atr*InpAtrStopMult, tpDist=slDist*InpRewardRisk;
   double lot=LotByRisk(slDist,sf); if(lot<=0) return;
   int digits=(int)SymbolInfoInteger(_Symbol,SYMBOL_DIGITS);
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(bias>0)
   { double sl=NormalizeDouble(ask-slDist,digits),tp=NormalizeDouble(ask+tpDist,digits);
     if(trade.Buy(lot,_Symbol,ask,sl,tp,"OmniAI session long")){ g_tradesToday++;
        Notify("Session LONG taken on "+_Symbol+" bias "+DoubleToString(bias,2)); } }
   else
   { double sl=NormalizeDouble(bid+slDist,digits),tp=NormalizeDouble(bid-tpDist,digits);
     if(trade.Sell(lot,_Symbol,bid,sl,tp,"OmniAI session short")){ g_tradesToday++;
        Notify("Session SHORT taken on "+_Symbol+" bias "+DoubleToString(bias,2)); } }
}

//+------------------------------------------------------------------+
//| NEWS FILTER: true while a high-impact event for this symbol's      |
//| currencies is inside the [before, after] window around now.        |
//| Uses the MT5 economic calendar (live terminal only; returns false  |
//| in the Strategy Tester, which is fine).                            |
//+------------------------------------------------------------------+
bool NewsBlackout()
{
   datetime now  = TimeCurrent();
   datetime from = now - InpNewsMinsAfter  * 60;   // events that just happened
   datetime to   = now + InpNewsMinsBefore * 60;   // events coming up

   string base  = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_BASE);
   string quote = SymbolInfoString(_Symbol, SYMBOL_CURRENCY_PROFIT);

   MqlCalendarValue values[];
   int n = CalendarValueHistory(values, from, to, NULL, NULL);
   for(int i=0; i<n; i++)
   {
      MqlCalendarEvent ev;
      if(!CalendarEventById(values[i].event_id, ev)) continue;
      if(InpNewsHighOnly && ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;

      MqlCalendarCountry ctry;
      if(!CalendarCountryById(ev.country_id, ctry)) continue;
      string cur = ctry.currency;
      if(cur==base || cur==quote)
         return(true);
   }
   return(false);
}

//+------------------------------------------------------------------+
//| MULTI-SYMBOL SCANNER setup: create per-symbol indicator handles   |
//+------------------------------------------------------------------+
void SetupWatchlist()
{
   string parts[];
   int k = StringSplit(InpWatchSymbols, ',', parts);
   if(k<=0) return;
   ArrayResize(g_watch,k); ArrayResize(g_wEmaF,k); ArrayResize(g_wEmaS,k);
   ArrayResize(g_wRsi,k);  ArrayResize(g_wAdx,k);
   g_watchCount=0;
   for(int i=0;i<k;i++)
   {
      string s=parts[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)<2) continue;
      if(!SymbolSelect(s,true)) { Print("Watchlist: symbol not found: ",s); continue; }
      int idx=g_watchCount;
      g_watch[idx] = s;
      g_wEmaF[idx] = iMA(s,_Period,20,0,MODE_EMA,PRICE_CLOSE);
      g_wEmaS[idx] = iMA(s,_Period,50,0,MODE_EMA,PRICE_CLOSE);
      g_wRsi[idx]  = iRSI(s,_Period,InpPeriods,PRICE_CLOSE);
      g_wAdx[idx]  = iADX(s,_Period,InpPeriods);
      if(g_wEmaF[idx]==INVALID_HANDLE || g_wEmaS[idx]==INVALID_HANDLE ||
         g_wRsi[idx]==INVALID_HANDLE  || g_wAdx[idx]==INVALID_HANDLE) continue;
      g_watchCount++;
   }
   Print("Watchlist active: ",g_watchCount," symbols.");
}

//+------------------------------------------------------------------+
//| Compact ensemble bias for a watchlist symbol (by index)           |
//+------------------------------------------------------------------+
double WatchBias(const int i)
{
   double emaF,emaS,rsi,adx,pdi,ndi,score=0,weight=0;
   if(RB(g_wEmaF[i],0,0,emaF) && RB(g_wEmaS[i],0,0,emaS) && emaS!=0)
   { double s=MathMin(MathAbs(emaF-emaS)/emaS*20.0,1.0);
     if(emaF>emaS) score+=s; else score-=s; weight+=s; }
   if(RB(g_wRsi[i],0,0,rsi))
   { if(rsi<30){double s=MathMin((30-rsi)/30.0,1.0);score+=s;weight+=s;}
     else if(rsi>70){double s=MathMin((rsi-70)/30.0,1.0);score-=s;weight+=s;} }
   if(RB(g_wAdx[i],0,0,adx) && RB(g_wAdx[i],1,0,pdi) && RB(g_wAdx[i],2,0,ndi))
   { if(adx>=25){double s=MathMin((adx-25)/25.0,1.0);
       if(pdi>ndi)score+=s; else score-=s; weight+=s;} }
   if(weight<=0) return(0);
   return(score/weight);
}

//+------------------------------------------------------------------+
//| Scan the basket and alert on the single best opportunity          |
//+------------------------------------------------------------------+
void MultiSymbolScan()
{
   int best=-1, bestDir=0; double bestConv=0;
   for(int i=0;i<g_watchCount;i++)
   {
      double b=WatchBias(i); double conv=MathAbs(b);
      if(conv>bestConv){ bestConv=conv; best=i; bestDir=(b>0?1:-1); }
   }
   if(best<0 || bestConv<InpMultiMinConv) return;
   string sym=g_watch[best];
   if(sym==g_lastScanSym && bestDir==g_lastScanDir) return;   // debounce
   g_lastScanSym=sym; g_lastScanDir=bestDir;
   Notify(StringFormat("WATCHLIST best move: %s %s  (conviction %.0f%%)",
          (bestDir>0?"LONG":"SHORT"), sym, bestConv*100.0));
}

//+------------------------------------------------------------------+
//| PATTERN SCANNER: alert on the patterns the user is watching       |
//+------------------------------------------------------------------+
bool Wants(const string key){ return(StringFind(InpWatchPatterns,key)>=0); }

void ScanPatterns()
{
   double o[],h[],l[],c[];
   if(CopyOpen(_Symbol,_Period,1,3,o)<3) return;
   if(CopyHigh(_Symbol,_Period,1,3,h)<3) return;
   if(CopyLow(_Symbol,_Period,1,3,l)<3)  return;
   if(CopyClose(_Symbol,_Period,1,3,c)<3) return;
   // arrays: index 2 = most recent closed bar
   int x=2, p=1;
   double body=MathAbs(c[x]-o[x]);
   double rng=(h[x]-l[x]); if(rng<=0) rng=1e-9;
   double upper=h[x]-MathMax(c[x],o[x]);
   double lower=MathMin(c[x],o[x])-l[x];

   if(Wants("doji") && body<=0.1*rng)
      Notify("DOJI on "+_Symbol+" — indecision, possible reversal.");
   if(Wants("hammer") && lower>2*body && upper<body)
      Notify("HAMMER on "+_Symbol+" — buyers stepped in (bullish).");
   if(Wants("star") && upper>2*body && lower<body)
      Notify("SHOOTING STAR on "+_Symbol+" — sellers rejected highs (bearish).");
   bool prevUp=c[p]>o[p], curUp=c[x]>o[x];
   if(Wants("engulfing") && curUp && !prevUp && c[x]>=o[p] && o[x]<=c[p])
      Notify("BULLISH ENGULFING on "+_Symbol+".");
   if(Wants("engulfing") && !curUp && prevUp && o[x]>=c[p] && c[x]<=o[p])
      Notify("BEARISH ENGULFING on "+_Symbol+".");

   if(Wants("squeeze"))
   {
      double bu,bl,atr;
      if(RB(hBands,1,0,bu)&&RB(hBands,2,0,bl)&&RB(hAtr,0,0,atr)&&atr>0)
         if((bu-bl)<3.0*atr) Notify("VOLATILITY SQUEEZE on "+_Symbol+" — breakout often follows.");
   }
   if(Wants("breakout"))
   {
      double hh=-DBL_MAX,ll=DBL_MAX,hi[],lo[];
      if(CopyHigh(_Symbol,_Period,1,20,hi)==20 && CopyLow(_Symbol,_Period,1,20,lo)==20)
      {
         for(int i=0;i<20;i++){ if(hi[i]>hh)hh=hi[i]; if(lo[i]<ll)ll=lo[i]; }
         double price=SymbolInfoDouble(_Symbol,SYMBOL_BID);
         if(price>=hh) Notify("RANGE BREAKOUT up on "+_Symbol+" ("+DoubleToString(hh,_Digits)+").");
         else if(price<=ll) Notify("RANGE BREAKDOWN on "+_Symbol+" ("+DoubleToString(ll,_Digits)+").");
      }
   }
   if(Wants("divergence"))
   {
      double cc[]; double rsiArr[];
      if(CopyClose(_Symbol,_Period,1,14,cc)==14 && CopyBuffer(hRsi,0,1,14,rsiArr)==14)
      {
         double p1=cc[0],p2=cc[13],r1=rsiArr[0],r2=rsiArr[13];
         if(p2>p1 && r2<r1) Notify("BEARISH RSI DIVERGENCE on "+_Symbol+".");
         if(p2<p1 && r2>r1) Notify("BULLISH RSI DIVERGENCE on "+_Symbol+".");
      }
   }
}

//+------------------------------------------------------------------+
//| Unified alert sink                                                |
//+------------------------------------------------------------------+
void Notify(const string msg)
{
   if(InpPopupAlert) Alert(msg);
   if(InpPushAlert)  SendNotification(msg);
   if(InpSoundAlert) PlaySound("alert.wav");
   Print("[ALERT] ",msg);
}

//+------------------------------------------------------------------+
//| CHART DRAWING: key support/resistance, prior day, pivots, round   |
//+------------------------------------------------------------------+
void HLine(const string name,const double price,const color clr,const string label)
{
   string n="omni_"+name;
   if(ObjectFind(0,n)<0) ObjectCreate(0,n,OBJ_HLINE,0,0,price);
   ObjectSetDouble(0,n,OBJPROP_PRICE,price);
   ObjectSetInteger(0,n,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,n,OBJPROP_STYLE,STYLE_DOT);
   ObjectSetInteger(0,n,OBJPROP_BACK,true);
   ObjectSetString(0,n,OBJPROP_TEXT,label);
}

void DrawKeyLevels()
{
   // Prior-day high/low
   if(InpDrawPrevDay)
   {
      double dh[],dl[];
      if(CopyHigh(_Symbol,PERIOD_D1,1,1,dh)==1) HLine("PDH",dh[0],clrTomato,"Prev Day High");
      if(CopyLow (_Symbol,PERIOD_D1,1,1,dl)==1) HLine("PDL",dl[0],clrDodgerBlue,"Prev Day Low");
   }
   // Donchian support/resistance (range high/low on current TF)
   if(InpDrawDonchian)
   {
      double hh=-DBL_MAX,ll=DBL_MAX,hi[],lo[];
      if(CopyHigh(_Symbol,_Period,1,20,hi)==20 && CopyLow(_Symbol,_Period,1,20,lo)==20)
      {
         for(int i=0;i<20;i++){ if(hi[i]>hh)hh=hi[i]; if(lo[i]<ll)ll=lo[i]; }
         HLine("RES",hh,clrOrangeRed,"Resistance (20)");
         HLine("SUP",ll,clrLimeGreen,"Support (20)");
      }
   }
   // Daily pivots
   if(InpDrawPivots)
   {
      double dh[],dl[],dc[];
      if(CopyHigh(_Symbol,PERIOD_D1,1,1,dh)==1 &&
         CopyLow (_Symbol,PERIOD_D1,1,1,dl)==1 &&
         CopyClose(_Symbol,PERIOD_D1,1,1,dc)==1)
      {
         double P=(dh[0]+dl[0]+dc[0])/3.0;
         double R1=2*P-dl[0], S1=2*P-dh[0];
         HLine("PP",P,clrGold,"Pivot");
         HLine("R1",R1,clrSalmon,"R1");
         HLine("S1",S1,clrAquamarine,"S1");
      }
   }
   // Nearest round number
   if(InpDrawRound)
   {
      double price=SymbolInfoDouble(_Symbol,SYMBOL_BID);
      double step=(_Digits>=3)?0.0100:1.0;            // 100 pips for FX-ish, 1.0 otherwise
      if(_Digits<=2) step=10.0;
      double rn=MathRound(price/step)*step;
      HLine("ROUND",rn,clrSilver,"Round "+DoubleToString(rn,_Digits));
   }
}

//+------------------------------------------------------------------+
//| STRATEGY ADVISOR: which approach fits this symbol right now?       |
//|  Quick walk over recent bars; ranks strategies by forward P&L.    |
//+------------------------------------------------------------------+
string RunStrategyAdvisor(const bool alert)
{
   int N=MathMax(InpAdvisorBars,150);
   double c[],emaF[],emaS[],rsi[],macd[],sig[],bu[],bl[],adx[],pdi[],ndi[];
   if(CopyClose(_Symbol,_Period,0,N,c)<N) return("(insufficient data)");
   if(CopyBuffer(hEmaF,0,0,N,emaF)<N) return("(no data)");
   if(CopyBuffer(hEmaS,0,0,N,emaS)<N) return("(no data)");
   if(CopyBuffer(hRsi,0,0,N,rsi)<N)   return("(no data)");
   if(CopyBuffer(hMacd,0,0,N,macd)<N) return("(no data)");
   if(CopyBuffer(hMacd,1,0,N,sig)<N)  return("(no data)");
   if(CopyBuffer(hBands,1,0,N,bu)<N)  return("(no data)");
   if(CopyBuffer(hBands,2,0,N,bl)<N)  return("(no data)");
   if(CopyBuffer(hAdx,0,0,N,adx)<N)   return("(no data)");
   if(CopyBuffer(hAdx,1,0,N,pdi)<N)   return("(no data)");
   if(CopyBuffer(hAdx,2,0,N,ndi)<N)   return("(no data)");

   string names[6]={"EMA crossover","RSI reversion","MACD momentum",
                    "Bollinger breakout","ADX trend","Donchian breakout"};
   double pnl[6]; int wins[6], trades[6];
   for(int s=0;s<6;s++){ pnl[s]=0; wins[s]=0; trades[s]=0; }

   for(int i=30;i<N-1;i++)
   {
      double fwd=(c[i+1]-c[i]);                 // next-bar move
      int dir;
      // EMA crossover
      dir=(emaF[i]>emaS[i])?1:-1; Acc(pnl,wins,trades,0,dir,fwd);
      // RSI reversion
      if(rsi[i]<30) Acc(pnl,wins,trades,1,1,fwd);
      else if(rsi[i]>70) Acc(pnl,wins,trades,1,-1,fwd);
      // MACD momentum
      double hN=macd[i]-sig[i], hP=macd[i-1]-sig[i-1];
      if(hN>0&&hN>hP) Acc(pnl,wins,trades,2,1,fwd);
      else if(hN<0&&hN<hP) Acc(pnl,wins,trades,2,-1,fwd);
      // Bollinger breakout
      if(c[i]>bu[i]) Acc(pnl,wins,trades,3,1,fwd);
      else if(c[i]<bl[i]) Acc(pnl,wins,trades,3,-1,fwd);
      // ADX trend
      if(adx[i]>=25){ dir=(pdi[i]>ndi[i])?1:-1; Acc(pnl,wins,trades,4,dir,fwd); }
      // Donchian breakout (20)
      if(i>=20)
      {
         double hh=-DBL_MAX,ll=DBL_MAX;
         for(int k=i-20;k<i;k++){ if(c[k]>hh)hh=c[k]; if(c[k]<ll)ll=c[k]; }
         if(c[i]>=hh) Acc(pnl,wins,trades,5,1,fwd);
         else if(c[i]<=ll) Acc(pnl,wins,trades,5,-1,fwd);
      }
   }

   int best=0; for(int s=1;s<6;s++) if(pnl[s]>pnl[best]) best=s;
   string report="Strategy fit for "+_Symbol+" ("+EnumToString(_Period)+"):\n";
   for(int s=0;s<6;s++)
   {
      double wr=(trades[s]>0)?(100.0*wins[s]/trades[s]):0.0;
      report+=StringFormat("  %-20s score %+.5f  win%% %.0f  (%d)\n",
                            names[s],pnl[s],wr,trades[s]);
   }
   report+="BEST FIT: "+names[best];
   if(alert) Print(report);
   Comment(report);
   return(names[best]);
}

void Acc(double &pnl[],int &wins[],int &trades[],const int s,const int dir,const double fwd)
{
   double r=dir*fwd; pnl[s]+=r; trades[s]++; if(r>0) wins[s]++;
}

//+------------------------------------------------------------------+
//| ON-CHART DASHBOARD                                                |
//+------------------------------------------------------------------+
void Lbl(const string name,const int x,const int y,const string txt,const color clr)
{
   string n="omni_dash_"+name;
   if(ObjectFind(0,n)<0) ObjectCreate(0,n,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,n,OBJPROP_CORNER,CORNER_LEFT_UPPER);
   ObjectSetInteger(0,n,OBJPROP_XDISTANCE,x);
   ObjectSetInteger(0,n,OBJPROP_YDISTANCE,y);
   ObjectSetInteger(0,n,OBJPROP_COLOR,clr);
   ObjectSetInteger(0,n,OBJPROP_FONTSIZE,9);
   ObjectSetString(0,n,OBJPROP_TEXT,txt);
}

void UpdateDashboard()
{
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   double dayPL=(g_dayStartEq>0)?(eq-g_dayStartEq):0.0;
   double dayPct=(g_dayStartEq>0)?(dayPL/g_dayStartEq*100.0):0.0;
   double dd=(g_peakEquity>0)?((g_peakEquity-eq)/g_peakEquity*100.0):0.0;
   color plc=(dayPL>=0)?clrLime:clrTomato;
   string status=g_kill?"HALTED (kill switch)":(GuardianAllows()?"OK to trade":"Paused (limit)");

   Lbl("0",10,18,"=== OMNI AI PARTNER ===",clrWhite);
   Lbl("1",10,34,"Status: "+status,g_kill?clrTomato:clrAqua);
   Lbl("2",10,50,"Equity: "+DoubleToString(eq,2),clrWhite);
   Lbl("3",10,66,StringFormat("Day P/L: %.2f (%.2f%%)",dayPL,dayPct),plc);
   Lbl("4",10,82,StringFormat("Drawdown: %.2f%%",dd),(dd>InpMaxDrawdownPct*0.5)?clrOrange:clrWhite);
   Lbl("5",10,98,"Open (EA): "+(string)CountMyPositions()+
                 "  Trades today: "+(string)g_tradesToday,clrWhite);
   Lbl("6",10,114,"Best strategy: "+g_bestStrategy,clrGold);
   Lbl("7",10,130,"News: "+(g_newsActive?"BLACKOUT (trades paused)":"clear")+
                  "   Watchlist: "+(string)g_watchCount,
                  g_newsActive?clrOrange:clrWhite);
}

//+------------------------------------------------------------------+
//| AI CHAT UI (chart objects) + WebRequest bridge                    |
//+------------------------------------------------------------------+
void CreateChatUI()
{
   if(ObjectFind(0,UI_INPUT)<0) ObjectCreate(0,UI_INPUT,OBJ_EDIT,0,0,0);
   ObjectSetInteger(0,UI_INPUT,OBJPROP_CORNER,CORNER_LEFT_LOWER);
   ObjectSetInteger(0,UI_INPUT,OBJPROP_XDISTANCE,10);
   ObjectSetInteger(0,UI_INPUT,OBJPROP_YDISTANCE,40);
   ObjectSetInteger(0,UI_INPUT,OBJPROP_XSIZE,360);
   ObjectSetInteger(0,UI_INPUT,OBJPROP_YSIZE,22);
   ObjectSetString(0,UI_INPUT,OBJPROP_TEXT,"ask me about this symbol...");

   if(ObjectFind(0,UI_ASK)<0) ObjectCreate(0,UI_ASK,OBJ_BUTTON,0,0,0);
   ObjectSetInteger(0,UI_ASK,OBJPROP_CORNER,CORNER_LEFT_LOWER);
   ObjectSetInteger(0,UI_ASK,OBJPROP_XDISTANCE,378);
   ObjectSetInteger(0,UI_ASK,OBJPROP_YDISTANCE,40);
   ObjectSetInteger(0,UI_ASK,OBJPROP_XSIZE,70);
   ObjectSetInteger(0,UI_ASK,OBJPROP_YSIZE,22);
   ObjectSetString(0,UI_ASK,OBJPROP_TEXT,"Ask AI");
   ObjectSetInteger(0,UI_ASK,OBJPROP_BGCOLOR,clrTeal);
   ObjectSetInteger(0,UI_ASK,OBJPROP_COLOR,clrWhite);

   if(ObjectFind(0,UI_ADV)<0) ObjectCreate(0,UI_ADV,OBJ_BUTTON,0,0,0);
   ObjectSetInteger(0,UI_ADV,OBJPROP_CORNER,CORNER_LEFT_LOWER);
   ObjectSetInteger(0,UI_ADV,OBJPROP_XDISTANCE,456);
   ObjectSetInteger(0,UI_ADV,OBJPROP_YDISTANCE,40);
   ObjectSetInteger(0,UI_ADV,OBJPROP_XSIZE,90);
   ObjectSetInteger(0,UI_ADV,OBJPROP_YSIZE,22);
   ObjectSetString(0,UI_ADV,OBJPROP_TEXT,"Best Strategy");
   ObjectSetInteger(0,UI_ADV,OBJPROP_BGCOLOR,clrIndigo);
   ObjectSetInteger(0,UI_ADV,OBJPROP_COLOR,clrWhite);
}

void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
{
   if(id!=CHARTEVENT_OBJECT_CLICK) return;
   if(sparam==UI_ADV)
   {
      g_bestStrategy=RunStrategyAdvisor(true);
      ObjectSetInteger(0,UI_ADV,OBJPROP_STATE,false);
      return;
   }
   if(sparam==UI_ASK)
   {
      string q=ObjectGetString(0,UI_INPUT,OBJPROP_TEXT);
      ObjectSetInteger(0,UI_ASK,OBJPROP_STATE,false);
      if(StringLen(q)<2){ Comment("Type a question first."); return; }
      Comment("Asking the AI brain... (needs Python serve.py running)");
      string ans=AskAI(q);
      g_lastAnswer=ans;
      Comment("Q: "+q+"\n\nAI: "+ans);
      return;
   }
}

//+------------------------------------------------------------------+
//| WebRequest to the Python agent: GET /api/run?action=ask&...       |
//+------------------------------------------------------------------+
string AskAI(const string question)
{
   string url=InpAIServerURL+"/api/run?action=ask&symbol="+UrlEncode(_Symbol)+
              "&timeframe="+TFToStr(_Period)+"&question="+UrlEncode(question);
   char data[]; char result[]; string rh;
   ResetLastError();
   int code=WebRequest("GET",url,NULL,NULL,8000,data,0,result,rh);
   if(code==-1)
   {
      int e=GetLastError();
      if(e==4014)
         return("WebRequest blocked. In MT5: Tools > Options > Expert Advisors > "
                "tick 'Allow WebRequest for listed URL' and add "+InpAIServerURL);
      return("Could not reach the AI brain ("+(string)e+"). Is Python serve.py running?");
   }
   if(code!=200) return("AI server returned HTTP "+(string)code+".");
   string body=CharArrayToString(result,0,WHOLE_ARRAY,CP_UTF8);
   return(ExtractJsonText(body));
}

string TFToStr(const ENUM_TIMEFRAMES tf)
{
   switch(tf){
      case PERIOD_M5:return("5m"); case PERIOD_M15:return("15m");
      case PERIOD_H1:return("1h"); case PERIOD_H4:return("4h");
      case PERIOD_D1:return("1d"); case PERIOD_W1:return("1w");
      default:return("1d"); }
}

string UrlEncode(const string s)
{
   string out=""; uchar bytes[];
   int n=StringToCharArray(s,bytes,0,WHOLE_ARRAY,CP_UTF8);
   for(int i=0;i<n;i++)
   {
      uchar ch=bytes[i];
      if(ch==0) continue;
      if((ch>='A'&&ch<='Z')||(ch>='a'&&ch<='z')||(ch>='0'&&ch<='9')||
         ch=='-'||ch=='_'||ch=='.'||ch=='~')
         out+=CharToString(ch);
      else
         out+=StringFormat("%%%02X",ch);
   }
   return(out);
}

//+------------------------------------------------------------------+
//| Pull the "text" string out of {"text":"..."} (handles \n \" )     |
//+------------------------------------------------------------------+
string ExtractJsonText(const string json)
{
   string key="\"text\":";
   int kp=StringFind(json,key); if(kp<0) return(json);
   int i=kp+StringLen(key);
   // skip spaces and opening quote
   while(i<StringLen(json) && StringGetCharacter(json,i)!='"') i++;
   i++; // past opening quote
   string out="";
   while(i<StringLen(json))
   {
      ushort ch=StringGetCharacter(json,i);
      if(ch=='\\' && i+1<StringLen(json))
      {
         ushort nx=StringGetCharacter(json,i+1);
         if(nx=='n') out+="\n";
         else if(nx=='t') out+="    ";
         else if(nx=='"') out+="\"";
         else if(nx=='\\') out+="\\";
         else if(nx=='/') out+="/";
         else out+=ShortToString(nx);
         i+=2; continue;
      }
      if(ch=='"') break;   // closing quote
      out+=ShortToString(ch);
      i++;
   }
   return(out);
}
//+------------------------------------------------------------------+
