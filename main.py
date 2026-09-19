#!/usr/bin/env python3
"""
Uncensored Coder - AI Code Generator
by BitJacker
"""

import sys
import yaml
import os
from core.code_generator import CodeGenerator
from core.model_loader import OllamaUnavailableError
from interface.cli import CLI

def banner():
    # Primary ASCII Art Banner - Left Aligned
    ascii_art = r"""
██╗   ██╗███╗   ██╗ ██████╗███████╗███╗   ██╗███████╗ ██████╗ ██████╗ ███████╗██████╗ 
██║   ██║████╗  ██║██╔════╝██╔════╝████╗  ██║██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
██║   ██║██╔██╗ ██║██║     █████╗  ██╔██╗ ██║███████╗██║   ██║██║  ██║█████╗  ██████╔╝
██║   ██║██║╚██╗██║██║     ██╔══╝  ██║╚██╗██║╚════██║██║   ██║██║  ██║██╔══╝  ██╔══██╗
╚██████╔╝██║ ╚████║╚██████╗███████╗██║ ╚████║███████║╚██████╔╝██████╔╝███████╗██║  ██║
 ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝╚══════╝╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝

██████╗ ██████╗ ██████╗ ███████╗██████╗ 
██╔════╝██╔═══██╗██╔══██╗██╔════╝██╔══██╗
██║     ██║   ██║██║  ██║█████╗  ██████╔╝
██║     ██║   ██║██║  ██║██╔══╝  ██╔══██╗
╚██████╗╚██████╔╝██████╔╝███████╗██║  ██║
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
"""
    print(ascii_art.strip())
    print("by BitJacker")
    print("\n")

def get_default_model():
    """Recupera il modello predefinito dal file config"""
    # Costruisce il percorso assoluto verso il file di configurazione
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'config', 'model_config.yaml')
    
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('default_model', 'dolphin-llama3')
    except Exception:
        # Se il file non esiste o ha errori, usiamo dolphin come fallback sicuro
        return 'dolphin-llama3'

def main():
    banner()
    
    try:
        # Recupera dinamicamente il modello dallo YAML
        target_model = get_default_model()
        
        # Inizializza il generatore con il modello scelto
        # Ora CodeGenerator userà internamente il ModelLoader aggiornato
        generator = CodeGenerator(model=target_model)

        print(f"🚀 Initializing with model: {target_model}")

        # Ensure the model is present before we drop into the prompt loop,
        # pulling it on first run. This surfaces connection/model problems
        # immediately instead of on the first generation attempt.
        generator.ensure_ready()

        print("🧞 Code Genie active! Type 'generate' or your request.")

        # Avvia l'interfaccia CLI
        cli = CLI(generator)
        cli.run()

    except KeyboardInterrupt:
        print("\n\n[!] Shutting down... Regards from BitJacker!")
        sys.exit(0)
    except OllamaUnavailableError as e:
        print(f"\n[!] Ollama not ready: {e}")
        sys.exit(2)
    except Exception as e:
        print(f"\n[!] Critical Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
