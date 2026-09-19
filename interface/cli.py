from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt, Confirm
from prompt_toolkit import prompt
import re

from core.model_loader import OllamaUnavailableError

# Default file extension per supported language, used when saving generated code.
LANG_EXTENSIONS = {
    "python": "py",
    "javascript": "js",
    "typescript": "ts",
    "java": "java",
    "cpp": "cpp",
    "rust": "rs",
    "go": "go",
    "html": "html",
    "css": "css",
    "sql": "sql",
}


class CLI:
    def __init__(self, generator):
        self.generator = generator
        self.console = Console()
        self.last_code = None
        self.last_lang = "python"

    def display_code(self, code: str, language: str):
        # 1. Aesthetic Highlighted View
        syntax = Syntax(code, language, theme="monokai", line_numbers=False, word_wrap=True)
        self.console.print(Panel(syntax, title="✨ Generated Code", border_style="green"))
        
        # 2. Raw View for Copy-Paste (No Borders)
        self.console.print("\n[bold white]👇 SELECT AND COPY THE CODE BELOW:[/bold white]")
        print("-" * 40)
        print(code)
        print("-" * 40)

    def run(self):
        self.console.print("[bold cyan]🧞 Code Genie active! Type 'generate', 'save' or your request.[/bold cyan]")
        
        while True:
            try:
                user_input = prompt('\n🧞 > ').strip()
                if not user_input: continue
                if user_input.lower() in ['exit', 'quit']: break

                # SAVE command handling
                if user_input.lower().startswith('save'):
                    if not self.last_code:
                        self.console.print("[red]No code available to save.[/red]")
                        continue
                    parts = user_input.split()
                    if len(parts) > 1:
                        fname = parts[1]
                    else:
                        ext = LANG_EXTENSIONS.get(self.last_lang, "txt")
                        fname = f"script.{ext}"
                    path = self.generator.save_to_file(self.last_code, fname)
                    self.console.print(f"[green]💾 Saved to {path}[/green]")
                    continue

                lang = self._detect_language(user_input)

                with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=self.console) as prog:
                    prog.add_task(description="🤔 Generating...")
                    self.last_code = self.generator.generate(user_input, lang)
                    self.last_lang = lang

                self.display_code(self.last_code, self.last_lang)

            except OllamaUnavailableError as e:
                self.console.print(f"[red]Ollama error: {e}[/red]")
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

    @staticmethod
    def _detect_language(user_input: str) -> str:
        """Pick a target language from the request text.

        Matches whole words and prefers the longest keyword so that
        "javascript" is not clobbered by the substring "java".
        """
        text = user_input.lower()
        candidates = [
            "typescript", "javascript", "python", "java", "cpp",
            "rust", "go", "html", "css", "sql",
        ]
        found = [c for c in candidates if re.search(rf"\b{re.escape(c)}\b", text)]
        if not found:
            return "python"
        # Longest match wins (e.g. "javascript" over "java").
        return max(found, key=len)
