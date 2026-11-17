# OCR + LLM — Invoice Data Extraction

![Python](https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square)
![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=flat-square&logo=googlegemini&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

[English](README.md) | [Español](README.es.md)

> Hackathon project for **Anti Loop Day**, Universidad Nacional de General Sarmiento, 2025.

## The problem

Manual data entry from invoices and receipts is slow and error-prone. The goal was to take a PDF or image and return structured data ready to validate and persist.

## The solution

A FastAPI service that combines **OCR** and an **LLM** to extract fields from invoices:

- Document type.
- Total amount.
- Date.
- Business name and tax ID (CUIT).
- Invoice type and number.
- CAE and point of sale.

The LLM output is validated with **Pydantic** schemas before returning it, so malformed or partial responses fail gracefully.

## Architecture

```mermaid
flowchart LR
    U[PDF / image] --> API[FastAPI]
    API --> OCR[Tesseract / pdf2image]
    OCR --> LLM[Gemini via LangChain]
    LLM --> SCHEMA[Pydantic validation]
    SCHEMA --> JSON[Structured JSON]
    API --> N8N[n8n workflow]
```

## Repository layout

```text
├── python_agent.py          # FastAPI app + OCR/LLM extraction
├── index.html               # demo UI
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── My workflow-n8n.json     # automation workflow
└── LICENSE
```

## Extracted data

| Field | Example |
|---|---|
| Document type | Factura A |
| Total amount | 125000.00 |
| Date | 2025-11-20 |
| Business name | Acme S.A. |
| CUIT | 30-12345678-9 |
| Invoice number | 0001-00001234 |
| CAE | 75123456789012 |

## My role

- FastAPI endpoint for file upload and extraction.
- OCR pipeline for PDFs and images.
- Prompt and schema design for reliable structured output.
- Validation layer with Pydantic.
- Docker setup and n8n workflow for downstream automation.

## Running locally

```bash
cp .env.example .env
# edit .env and set GEMINI_API_KEY
docker compose up --build
```

The API is exposed on port `8000`. The demo UI is `index.html`.

## Stack

`Python` · `FastAPI` · `LangChain` · `Gemini` · `Tesseract` · `pdf2image` · `Pydantic` · `Docker` · `n8n`

## Notes

- No API keys or real webhook URLs are committed.
- The n8n workflow points to the local `python_agent` service.
- Code published for portfolio purposes under the MIT license.
