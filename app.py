from textual.app import App
from textual.widgets import Header, Footer, Static

class MyApp(App):
    def compose(self):
        yield Header()
        yield Static("Hello from Textual!")
        yield Footer()

if __name__ == "__main__":
    MyApp().run()