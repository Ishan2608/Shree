# Shree_v2 (Work in Progress)

Shree_v2 is an AI financial analyst assistant tailored for Indian retail investors.

## Virtual Environment

Create and activate the environment:
```bash
# create environment.
python -m venv venv
# activate env - Windows
venv\Scripts\activate

# activate env - macOS/Linux
source venv/bin/activate
```

## Dependencies

List of dependencies: `fastapi`, `uvicorn[standard]`, `google-adk`, `mcp`, `pydantic-settings`, `google-generativeai`, `yfinance`, `pandas`, `numpy`, `tavily-python`, `newsapi-python`, `PyPDF2`, `openpyxl`, `python-multipart`, `torch`, `transformers`, `accelerate`, and `chronos-forecasting`.

Install dependencies:
```bash
pip install --upgrade pip
pip install fastapi uvicorn[standard] google-adk mcp pydantic-settings google-generativeai yfinance pandas numpy tavily-python newsapi-python PyPDF2 openpyxl python-multipart torch transformers accelerate
pip install git+[https://github.com/amazon-science/chronos-forecasting.git](https://github.com/amazon-science/chronos-forecasting.git)
```

## Requirements File

Create `requirements.txt`:
```bash
pip freeze > requirements.txt
```

Install from `requirements.txt`:
```bash
pip install -r requirements.txt
```

## API Keys Required

Create a `.env` file and include the following keys:
* GEMINI_API_KEY
* TAVILY_API_KEY
* NEWS_API_KEY
