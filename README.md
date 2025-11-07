# Expensomatic 🤖

AI-powered expense automation for Kantata using OpenAI Vision and Playwright.

## Features

- **AI-Powered Receipt Analysis**: Uses OpenAI GPT-4 Vision to extract amount, currency, category, and date from receipts
- **Automatic Categorization**: Intelligently categorizes expenses based on receipt content
- **Multi-Currency Support**: Handles GBP, USD, EUR, and other currencies
- **PDF Support**: Processes both images (JPG, PNG) and PDF receipts
- **Batch Processing**: Processes up to 15 receipts per expense claim
- **SSO Integration**: Uses Microsoft Edge SSO for seamless authentication

## Setup

### 1. Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install Playwright browsers
playwright install msedge

# Install Poppler for PDF support (macOS)
brew install poppler
```

### 2. Configure

Edit `config.yaml`:
- Add your OpenAI API key
- Update category IDs if needed

### 3. Prepare Receipts

Place receipt files (JPG, PNG, PDF) in the `receipts/` directory.

## Usage

```bash
python expense_automation.py
```

The script will:
1. Open Edge with your SSO session
2. Analyze all receipts in `receipts/` folder using AI
3. Create expense claim with extracted data
4. Upload receipts to each expense item
5. Save the claim for your review
6. Move processed receipts to a dated subfolder

## Workflow

```
receipts/
  ├── receipt1.jpg
  ├── receipt2.pdf
  └── receipt3.jpg

        ↓ (automation runs)

receipts/
  └── November 7 20:06/  ← processed receipts moved here
      ├── receipt1.jpg
      ├── receipt2.pdf
      └── receipt3.jpg
```

## Output

- **Final Screenshot**: `screenshots/[timestamp]_final_expense_report.png`
- **Organized Receipts**: Moved to dated subfolder for record keeping
- **Console Output**: Detailed progress and extracted information

## Notes

- Claims are **saved but not submitted** - review before submitting
- Maximum **15 expenses per claim** - larger batches split automatically
- **SSO required** - uses your existing Edge browser session
- **Categories**: Breakfast, Lunch, Dinner, Parking, Flights, Taxi, Train, Office Supplies, Client Meal, Software, Other

## Troubleshooting

**Browser not opening?**
- Ensure Microsoft Edge is installed
- Check that SSO session is active

**PDF errors?**
- Install Poppler: `brew install poppler`

**OpenAI errors?**
- Verify API key in `config.yaml`
- Check API quota/balance

## Requirements

- Python 3.8+
- Microsoft Edge (for SSO)
- OpenAI API key
- Poppler (for PDF support)

