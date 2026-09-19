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

## 🧪 Development & Tests

The core logic ships with a fully offline test suite (the `ollama` client is
mocked, so no server or model download is required):

```bash
pip install -r requirements.txt
pytest tests/ -q
```

---

**Made with 💀 by [BitJacker](https://github.com/BitJacker)**

**Uncensored Coder** - Because code should be free 🔓
