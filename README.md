<div align="center">

# 🎓 RadarCursos

**Radar automático de cursos gratuitos de Tecnologia no ensino superior brasileiro**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-1.62-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-ativo-brightgreen)]()

</div>

---

## 📖 Sobre

O **RadarCursos** é um script Python que busca automaticamente por **cursos gratuitos de tecnologia** com vagas abertas no ensino superior brasileiro (graduação, pós-graduação, MBA, mestrado e doutorado), tanto presenciais quanto EaD.

Ao terminar, gera um **relatório HTML interativo** com filtros por área, nível e status da vaga — abrindo automaticamente no navegador.

### ✨ O que ele faz

- 🔍 Realiza **32 buscas** no DuckDuckGo por cursos de tecnologia gratuitos
- 🟢 Classifica cada resultado como **Aberto**, **Provável** ou **Encerrado** automaticamente
- 🏛️ Identifica a **instituição de ensino** (UFMG, USP, IFSP, etc.)
- 🔗 Extrai o **link direto** para a faculdade (sem redirects)
- 📄 Gera um **relatório HTML** com cards filtrável por área, nível e status
- 💾 Salva histórico completo em banco de dados SQLite
- 🚫 Remove resultados **duplicados** automaticamente

---

## 🎯 Áreas monitoradas

| Graduação / Tecnólogo | Pós-graduação / MBA | Mestrado / Doutorado |
|---|---|---|
| Ciência da Computação | Especialização em IA | Mestrado em Computação |
| Análise e Dev. de Sistemas | Especialização em Dados | Doutorado em Computação |
| Engenharia de Software | Especialização em Segurança | Mestrado em IA |
| Sistemas de Informação | MBA em Gestão de TI | |
| Segurança da Informação / Cibersegurança | Pós em Dev. de Software | |
| Ciência de Dados | | |
| Inteligência Artificial | | |
| Redes de Computadores | | |
| Desenvolvimento Web / Mobile | | |
| Jogos Digitais | | |
| Cloud Computing / IoT | | |
| UX Design / Gestão de TI | | |

---

## 🚀 Como usar

### Pré-requisitos

- Python 3.10 ou superior
- Windows (o `.bat` é para Windows; no Linux/Mac basta rodar `python radar.py`)

### Instalação

```bash
# Clone o repositório
git clone https://github.com/HenkWilliam/radarcursos.git
cd RadarCursos

# Crie e ative o ambiente virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/Mac

# Instale as dependências
pip install playwright
playwright install chromium
```

### Execução

**Windows:** Execute o `radar.bat`

**Terminal:**
```bash
python radar.py
```

Ao terminar, o `relatorio.html` é aberto automaticamente no navegador com todos os resultados.

---

## 📊 Relatório HTML

O relatório gerado inclui:

- **Cards** para cada curso encontrado com título, instituição, área, nível e link direto
- **Badge de status** 🟢 Aberto / 🟡 Provável / 🔴 Encerrado
- **Filtros** por área de curso, nível e status de vaga
- **Busca** por texto livre (título, instituição, descrição)
- Por padrão exibe **apenas vagas abertas e prováveis**

> ⚠️ **Atenção:** O status é estimado automaticamente com base em palavras-chave e datas encontradas na descrição. Sempre confirme no link oficial da instituição.

---

## 🏗️ Estrutura do projeto

```
RadarCursos/
├── radar.py          # Script principal
├── config.json       # Áreas, instituições e palavras-chave configuráveis
├── radar.bat         # Atalho de execução (Windows)
├── .gitignore
├── README.md
└── logs/
    └── radar.log     # Log da última execução
```

> Os arquivos `cursos.db`, `relatorio.html` e `.venv/` são gerados localmente e não são versionados.

---

## ⚙️ Configuração

Edite o [`config.json`](config.json) para personalizar:

- **`area`** — palavras-chave de área para filtrar resultados
- **`palavras_aberto`** — termos que indicam vaga aberta (edital, inscrições, etc.)
- **`palavras_gratuito`** — termos que indicam curso gratuito
- **`instituicoes_conhecidas`** — lista de universidades/institutos para detecção automática

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Sugestões:

- Adicionar novas áreas de busca em `config.json`
- Melhorar a detecção de instituições
- Adicionar suporte a outras fontes além do DuckDuckGo
- Criar notificações por e-mail ou WhatsApp quando vaga nova for encontrada

---

## 📄 Licença

MIT — veja [LICENSE](LICENSE) para detalhes.

---

<div align="center">
Feito com 🐍 Python + 🎭 Playwright
</div>
