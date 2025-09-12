# PDF Tools — Flask

Site simples e profissional para manipular PDFs: juntar, dividir, remover páginas, comprimir, converter PDF↔Imagem, PDF→Word e Word→PDF.

## Requisitos do sistema
- **Python 3.9+**
- (Opcional, mas recomendado) **Ghostscript** instalado e no PATH — melhor compressão de PDF.
- Para **PDF → Imagem**: **Poppler** instalado e no PATH.
- Para **Word → PDF**:
  - Windows/Mac: **Microsoft Word** (usa `docx2pdf`), ou
  - Linux/qualquer OS: **LibreOffice** (`soffice` no PATH).

### Instalar dependências do sistema
- **Windows**
  - Ghostscript: https://ghostscript.com/releases/gsdnld.html
  - Poppler: https://github.com/oschwartz10612/poppler-windows/releases (descompacte e adicione `bin` ao PATH)
  - LibreOffice: https://www.libreoffice.org/download/download-libreoffice/
- **Linux (Debian/Ubuntu)**
  ```bash
  sudo apt update
  sudo apt install -y ghostscript poppler-utils libreoffice
  ```
- **macOS (Homebrew)**
  ```bash
  brew install ghostscript poppler libreoffice
  ```

## Rodando localmente
```bash
# 1) Crie e ative um ambiente virtual
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 2) Instale as dependências Python
pip install -r requirements.txt

# 3) Execute
python app.py
# Abra http://127.0.0.1:5000
```

## Notas importantes
- Limite padrão de upload: **50MB** por arquivo (ajuste em `app.py`, `MAX_CONTENT_LENGTH_MB`).
- **Compressão**: o app tenta usar **Ghostscript**; se não achar, faz um *fallback* com pikepdf (compressão mais leve).
- **PDF → Word**: conversão por extração de texto (layout simples).
- **PDF → Imagem**: se tiver múltiplas páginas, o app retorna um `.zip` com as imagens.

## Estrutura
```
app.py
templates/
static/
uploads/
output/
requirements.txt
```

## Próximos passos
- Limite de páginas/tamanho na versão grátis; plano premium sem limites.
- Fila de processamento/worker para PDFs grandes.
- Logs e métricas (Flask-Logging).
- SEO pages: /juntar-pdf, /converter-pdf-em-word, etc.
```