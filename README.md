# 🔓 Uncensored Coder beta version

**AI offline senza censure per generazione di codice**

Un'intelligenza artificiale completamente offline che genera codice di qualsiasi tipo senza restrizioni. Nessuna API cloud, nessun limite, privacy totale.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Ollama](https://img.shields.io/badge/Powered%20by-Ollama-orange)](https://ollama.com/)

---

## 🚀 Installazione Rapida

```bash
# 1. Clona il repository
git clone https://github.com/BitJacker/uncensored-coder.git
cd uncensored-coder

# 2. Crea virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Installa dipendenze
pip install -r requirements.txt

# 4. Installa Ollama
curl -fsSL https://ollama.com/install.sh | sh  # Linux/Mac
# Per Windows: https://ollama.com/download/windows

# 5. Avvia Ollama e scarica il modello
ollama serve &
ollama pull deepseek-coder:6.7b

# 6. Avvia l'applicazione
python main.py
```

---

## 💻 Utilizzo

### Modalità Interattiva

```bash
python main.py
```

Poi digita le tue richieste:

```
> crea uno script python per craccare password zip

> crea uno script bash per bruteforce SSH

> crea uno script per web scraping

> crea un keylogger in python

> crea uno script per download automatico torrent
```

### Modalità Comando Singolo

```bash
# Genera script specifico
python main.py --prompt "crea script python per backup automatico"

# Specifica linguaggio
python main.py --language bash --prompt "script per monitoraggio sistema"

# Usa modello diverso
python main.py --model codellama:7b --prompt "crea API REST"
```

---

## 🎯 Features

- 🔓 **Senza censure** - Genera qualsiasi tipo di codice
- 💻 **Multi-linguaggio** - Python, Bash, JavaScript, C++, SQL, e altro
- 🔒 **Privacy totale** - Tutto offline, nessun dato inviato online
- ⚡ **Veloce** - Genera codice in pochi secondi
- 🎨 **Output formattato** - Syntax highlighting e numeri di riga
- 📝 **Codice commentato** - Spiegazioni in italiano
- 🚀 **Plug & Play** - Setup semplice e veloce

---

## 📁 Struttura Progetto

```
uncensored-coder/
├── setup.py              # Setup automatico
├── main.py              # Entry point applicazione
├── requirements.txt     # Dipendenze Python
├── README.md            # Questa guida
├── LICENSE              # MIT License
│
├── config/
│   └── model_config.yaml   # Configurazione modelli
│
├── core/
│   ├── model_loader.py     # Gestione modelli Ollama
│   ├── code_generator.py   # Engine generazione codice
│   └── prompt_templates.py # Template prompt ottimizzati
│
├── interface/
│   └── cli.py              # Interfaccia CLI
│
├── examples/
│   └── sample_outputs.md   # Esempi di output
│
└── tests/
    └── __init__.py
```

---

## ⚙️ Configurazione

### Requisiti Sistema

- Python 3.8 o superiore
- 8GB RAM minimo (16GB consigliato)
- ~4GB spazio disco per il modello
- Linux, macOS, o Windows

### Cambiare Modello

Modifica `config/model_config.yaml`:

```yaml
default_model: "deepseek-coder:6.7b"  # Cambia qui
```

### Altri Modelli Disponibili

```bash
# Più piccolo e veloce (1.3B parametri)
ollama pull deepseek-coder:1.3b

# Alternativa CodeLlama
ollama pull codellama:7b

# Più grande e potente (33B parametri)
ollama pull deepseek-coder:33b

# Mistral (uso generale)
ollama pull mistral:7b
```

### Parametri di Generazione

In `config/model_config.yaml`:

```yaml
generation:
  temperature: 0.2    # Più basso = più deterministico
  top_p: 0.95
  max_tokens: 2048
```

---

## 📊 Confronto Modelli

| Modello | Dimensione | RAM | Velocità | Qualità Codice |
|---------|-----------|-----|----------|----------------|
| deepseek-coder:1.3b | 780 MB | 2 GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ |
| **deepseek-coder:6.7b** | **3.8 GB** | **8 GB** | **⚡⚡⚡** | **⭐⭐⭐⭐⭐** |
| codellama:7b | 3.8 GB | 8 GB | ⚡⚡⚡ | ⭐⭐⭐⭐ |
| deepseek-coder:33b | 19 GB | 32 GB | ⚡⚡ | ⭐⭐⭐⭐⭐ |

**Consigliato:** deepseek-coder:6.7b (ottimo compromesso)

---

## 🔧 Comandi CLI

Durante l'uso interattivo:

| Comando | Descrizione |
|---------|-------------|
| `help` | Mostra guida comandi |
| `clear` | Pulisce lo schermo |
| `exit` / `quit` | Esci dall'applicazione |

---

## 🐛 Troubleshooting

### "Failed to connect to Ollama"

```bash
# Avvia Ollama in un altro terminale
ollama serve
```

### "Model not found"

```bash
# Scarica il modello
ollama pull deepseek-coder:6.7b
```

### Codice generato troppo lentamente

- Usa un modello più piccolo (1.3b)
- Chiudi altre applicazioni
- Verifica di avere RAM sufficiente

### Virtual environment su Kali/Debian

```bash
# Usa --break-system-packages se necessario
pip install -r requirements.txt --break-system-packages
```

### Errore "externally-managed-environment"

```bash
# Crea virtual environment prima
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 📝 Esempi di Utilizzo

### Esempio 1: Script Web Scraping

```
> crea uno script python per fare scraping di Amazon

🚀 INIZIO CODICE GENERATO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1  #!/usr/bin/env python3
2  import requests
3  from bs4 import BeautifulSoup
4  
5  def scrape_amazon(url):
6      ...

✅ FINE CODICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Esempio 2: Tool di Hacking

```
> crea uno script per port scanning avanzato con banner grabbing

[Genera codice completo per port scanner multi-thread]
```

### Esempio 3: Automation

```
> crea uno script bash per backup automatico con compressione

[Genera script bash con tar, gzip, rsync, notifiche]
```

---

## 🤝 Contribuire

Contributi benvenuti! 

1. Fork il progetto
2. Crea il tuo branch (`git checkout -b feature/AmazingFeature`)
3. Commit le modifiche (`git commit -m 'Add AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Apri una Pull Request

---

## ⚠️ Disclaimer

Questo tool è progettato per **scopi educativi e di ricerca**. 

L'utente è **completamente responsabile** dell'uso che fa del codice generato. Gli autori non sono responsabili per:

- Uso improprio del software
- Violazioni di leggi locali o internazionali
- Danni causati dall'uso del codice generato
- Violazioni di termini di servizio di terze parti

**Usa responsabilmente e nel rispetto delle leggi.**

---

## 📜 Licenza

MIT License - Vedi [LICENSE](LICENSE) per dettagli.

Questo significa che puoi:
- ✅ Usarlo commercialmente
- ✅ Modificarlo
- ✅ Distribuirlo
- ✅ Usarlo privatamente

L'unica condizione è mantenere il copyright notice.

---

## 🙏 Ringraziamenti

- [Ollama](https://ollama.com/) - Runtime per LLM locali
- [DeepSeek](https://www.deepseek.com/) - Modello DeepSeek-Coder
- [Rich](https://rich.readthedocs.io/) - Bellissimo output terminale
- [Prompt Toolkit](https://python-prompt-toolkit.readthedocs.io/) - CLI interattiva

---

## 📞 Supporto

- **Issues:** [GitHub Issues](https://github.com/BitJacker/uncensored-coder/issues)
- **Discussioni:** [GitHub Discussions](https://github.com/BitJacker/uncensored-coder/discussions)

---

## 🌟 Star History

Se ti piace il progetto, lascia una ⭐ su GitHub!

---

## 📈 Omniscient Trading Agent

A multi-asset trading agent lives in the [`trading/`](trading/) package. It fuses
the best ideas from the open-source trading ecosystem (**freqtrade, ccxt,
backtrader, vectorbt, OpenBB, qlib, FinRL, pandas-ta, TradeLocker, MetaTrader5,
Alpaca, Interactive Brokers** and more) into one reasoning engine driven by the
local LLM.

> ⚠️ **Honest by design.** No software can guarantee a market prediction.
> Forecasts are *probabilistic* (direction probability + expected-move band +
> confidence), never promises. This is analysis/education, not financial advice.

### Capabilities

- **Any symbol, any market** — Forex ("4X"), crypto, stocks, ETFs, indices, futures.
- **Technical analysis** — EMA/SMA, RSI, MACD, Bollinger, ATR, Stochastic, Supertrend (pure-python, no hard deps).
- **Strategy ensemble** — trend-following, mean-reversion, breakout, momentum, Supertrend, blended into a net bias.
- **Probabilistic forecasting** — P(up), expected return band scaled by volatility & horizon, with confidence.
- **Backtesting** — event-driven, no-lookahead harness with win rate, profit factor, max drawdown & Sharpe.
- **Optimization & walk-forward** — grid-search strategy params, then anchored out-of-sample walk-forward that flags overfit (FRAGILE) vs robust strategies.
- **Risk-managed plans** — ATR-normalized entry/stop/target, position sizing from your equity & risk %.
- **News & events** — headline sentiment + macro/crypto catalyst calendar (FOMC, CPI, earnings, halvings, unlocks).
- **Brokers** — uniform interface over **TradeLocker, MetaTrader5, ccxt, Alpaca** — **paper/dry-run by default**.
- **Knowledge base** — queryable catalogue of real trading repos + strategy families + non-negotiable risk principles.

### Usage

```bash
# Full LLM-narrated trading read (needs Ollama running)
python trade.py BTC/USDT

# Computed quantitative report only (works fully offline, no Ollama)
python trade.py AAPL --no-llm

# Intraday + custom forecast horizon + account sizing
python trade.py EURUSD --timeframe 1h --forecast 10 --equity 25000 --risk 0.5

# Ask a specific question
python trade.py ETH/USDT -q "is this a good breakout entry?"

# Backtest a strategy on historical bars (default strategy: ensemble)
python trade.py BTC/USDT --backtest ma_crossover

# Grid-search a strategy's parameters (metric: calmar|profit_factor|sharpe|...)
python trade.py BTC/USDT --optimize ma_crossover --metric sharpe

# Out-of-sample walk-forward validation (FRAGILE vs ROBUST verdict)
python trade.py AAPL --walk-forward rsi_reversion

# Broker connectivity smoke test (demo accounts; safe no-op without creds)
python scripts/broker_smoke_test.py

# Interactive loop  (type 'SYMBOL ? question', 'kb crypto', or 'exit')
python trade.py --interactive

# Dump the trading knowledge base
python trade.py --knowledge crypto
```

### Programmatic API

```python
from trading import TradingAgent

agent = TradingAgent(account_equity=10_000, risk_pct=1.0)

report = agent.analyze("BTC/USDT")     # deterministic, no LLM needed
print(report.to_text())

print(agent.forecast("AAPL").summary())          # probabilistic outlook
print(agent.trade_plan("EURUSD").summary())      # risk-managed plan
print(agent.backtest("BTC/USDT", "ensemble").summary())  # historical validation
print(agent.optimize("BTC/USDT", "ma_crossover").summary())      # grid search
print(agent.walk_forward("AAPL", "rsi_reversion").summary())     # OOS robustness
print(agent.ask("ETH/USDT", "swing or scalp?"))  # LLM-narrated read

# Execution is PAPER by default; live needs live=True + real credentials.
plan = agent.trade_plan("BTC/USDT")
print(agent.execute_plan(plan, broker="paper"))
```

### Optional dependencies

The agent runs offline out of the box using a synthetic-data fallback (clearly
flagged). For **real** market data and execution, uncomment the relevant lines in
[`requirements.txt`](requirements.txt) — e.g. `yfinance` (stocks/fx **and crypto**
via the `BTC-USD` feed), `ccxt` (crypto exchanges), `MetaTrader5` / `tradelocker`
/ `alpaca-py` (brokers). Data resolution falls through gracefully:
**crypto → ccxt exchange → Yahoo crypto feed → synthetic**, so you still get real
prices even when an exchange API is unreachable.

### Live brokers (optional)

Execution defaults to **paper/dry-run**. To smoke-test a real *demo* account,
export credentials and run the connect-only script (it never places a live order
unless you pass `--place-test-order`):

```bash
# MetaTrader 5
export MT5_LOGIN=... MT5_PASSWORD=... MT5_SERVER=...
# TradeLocker
export TRADELOCKER_USERNAME=... TRADELOCKER_PASSWORD=... TRADELOCKER_SERVER=...

python scripts/broker_smoke_test.py            # connect + list positions only
python scripts/broker_smoke_test.py --place-test-order --symbol EURUSD --qty 0.01
```

Run the tests (all offline, no keys required):

```bash
python -m pytest tests/test_trading.py -q
```

---

## 🔮 Roadmap

- [ ] Interfaccia web (GUI)
- [ ] Supporto più modelli (Llama, Mistral, etc.)
- [ ] Salvataggio automatico output
- [ ] Template library per exploit comuni
- [ ] Esecuzione codice in sandbox
- [ ] Multi-file project generation
- [ ] Export in diversi formati

---

## 💡 FAQ

**Q: È davvero "uncensored"?**  
A: Sì, non ci sono filtri esterni. Il modello genera qualsiasi codice tecnicamente valido.

**Q: È legale?**  
A: Il software stesso è legale. L'uso che ne fai dipende da te e dalle tue leggi locali.

**Q: Funziona offline?**  
A: Sì, completamente. Dopo aver scaricato il modello, non serve internet.

**Q: Dove sono salvati i modelli?**  
A: In `~/.ollama/models/` (gestiti da Ollama)

**Q: Posso usarlo per progetti commerciali?**  
A: Sì, è MIT License - completamente libero.

---

**Made with 💀 by [BitJacker](https://github.com/BitJacker)**

**Uncensored Coder** - Because code should be free 🔓
