# Expensomatic 🤖

AI-powered expense automation for Kantata using OpenAI Vision and Playwright.

## Features

- **AI-Powered Receipt Analysis**: Uses OpenAI GPT-4 Vision to extract amount, currency, category, and date from receipts
- **Automatic Categorization**: Intelligently categorizes expenses based on receipt content
- **Multi-Currency Support**: Handles GBP, USD, EUR, INR, CHF, and other currencies
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
- Configure date override settings:
  - `override_old_dates: true` - Automatically adjust dates older than 30 days (default: true)
  - `max_days_old: 30` - Maximum age of expenses in days (default: 30)

### 3. Prepare Receipts

Place receipt files (JPG, PNG, PDF) in the `receipts/` directory.

## Usage

```bash
python expense_automation.py
```

The script will:
1. Open Edge with your SSO session
2. For each batch of up to 15 receipts:
   - Analyze receipts using AI
   - Move any that fail analysis to `receipts/failed/` folder
   - Create expense claim with extracted data
   - Upload receipts to each expense item
   - Save the claim for your review
   - Move processed receipts to a dated subfolder
3. Process continues until all receipts are handled

## Workflow

```
receipts/
  ├── receipt1.jpg
  ├── receipt2.pdf
  ├── receipt3.jpg
  └── bad_image.jpg

        ↓ (automation runs)

receipts/
  ├── failed/  ← failed receipts moved here
  │   └── bad_image.jpg
  └── November 7 20:06/  ← processed receipts moved here
      ├── receipt1.jpg
      ├── receipt2.pdf
      └── receipt3.jpg
```

## Output

- **Final Screenshot**: `screenshots/[timestamp]_final_expense_report.png`
- **Processed Receipts**: Moved to dated subfolder for record keeping
- **Failed Receipts**: Moved to `receipts/failed/` folder (if any analysis failures)
- **Console Output**: Detailed progress and extracted information

## Notes

- Claims are **saved but not submitted** - review before submitting
- Maximum **15 expenses per claim** - larger batches split automatically
- Each batch is **analyzed and submitted immediately** before moving to the next
- **Manual confirmation required** between batches - verify save was successful before continuing
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

