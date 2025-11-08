#!/usr/bin/env python3
"""
Expensomatic - AI-powered expense claim automation
Analyzes receipts with OpenAI Vision and automates Kantata expense submission
"""

import os
import json
import asyncio
import base64
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import io

from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import yaml
from openai import OpenAI
from pdf2image import convert_from_path
from PIL import Image


class Expensomatic:
    """Automates Kantata expense claim submission with AI receipt analysis"""
    
    CATEGORY_MAP = {
        'Breakfast': 'a08Tl00000KnFXLIA3',
        'Lunch': 'a08Tl00000KnFXLIA3',
        'Dinner': 'a08Tl00000KnFX7IAN',
        'Parking': 'a08Tl00000KnFXTIA3',
        'Transport: Flights': 'a08Tl00000KnFXCIA3',
        'Transport: Taxi': 'a08Tl00000KnFXRIA3',
        'Transport: Train': 'a08Tl00000KnFXGIA3',
        'Office Supplies': 'a08Tl00000KnFXAIA3',
        'Client Meal': 'a08Tl00000KnFXJIA3',
        'Software': 'a08Tl00000KnFXAIA3',
        'Other': 'a08Tl00000KnFX6IAN',
    }
    
    CURRENCY_SYMBOLS = {'GBP': '£', 'USD': '$', 'EUR': '€', 'INR': '₹', 'CHF': 'CHF'}
    
    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        Path(self.config['screenshot_dir']).mkdir(exist_ok=True)
        
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    async def init_browser(self):
        """Initialize Edge browser with persistent SSO session"""
        playwright = await async_playwright().start()
        print("🔐 Initializing browser...")
        
        user_data_dir = Path.home() / '.playwright-expense-automation'
        user_data_dir.mkdir(exist_ok=True)
        
        self.context = await playwright.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,
            channel='msedge',
            viewport={'width': 1280, 'height': 800},
            args=['--window-size=1280,800']
        )
        
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        print("✓ Browser ready")
    
    def pdf_to_image(self, pdf_path: str) -> Optional[str]:
        """Convert PDF first page to base64 image"""
        try:
            images = convert_from_path(pdf_path, first_page=1, last_page=1)
            if not images:
                return None
            
            img_bytes = io.BytesIO()
            images[0].save(img_bytes, format='JPEG')
            return base64.b64encode(img_bytes.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"❌ PDF error: {e}")
            if "poppler" in str(e).lower():
                print("   Install poppler: brew install poppler")
            return None
    
    def adjust_date_if_too_old(self, date_str: str) -> tuple[str, bool]:
        """Check if date is older than max_days_old and adjust if needed
        
        Returns:
            tuple: (adjusted_date_str, was_adjusted)
        """
        if not date_str:
            return date_str, False
        
        override_enabled = self.config.get('override_old_dates', True)
        max_days = self.config.get('max_days_old', 30)
        
        if not override_enabled:
            return date_str, False
        
        try:
            from datetime import datetime as dt, timedelta
            receipt_date = dt.strptime(date_str, '%Y-%m-%d')
            today = dt.now()
            days_old = (today - receipt_date).days
            
            if days_old > max_days:
                # Set to exactly max_days ago
                adjusted_date = today - timedelta(days=max_days)
                adjusted_date_str = adjusted_date.strftime('%Y-%m-%d')
                return adjusted_date_str, True
            
            return date_str, False
            
        except Exception:
            return date_str, False
    
    def analyze_receipt_with_openai(self, image_path: str) -> Optional[Dict]:
        """Analyze receipt (image or PDF) using OpenAI Vision API"""
        try:
            api_key = self.config.get('openai_api_key') or os.getenv('OPENAI_API_KEY')
            if not api_key:
                print("❌ OpenAI API key not found in config.yaml or OPENAI_API_KEY")
                return None
            
            client = OpenAI(api_key=api_key)
            
            # Handle PDF or image
            if image_path.lower().endswith('.pdf'):
                base64_image = self.pdf_to_image(image_path)
                if not base64_image:
                    return None
            else:
                with open(image_path, "rb") as f:
                    base64_image = base64.b64encode(f.read()).decode('utf-8')
            
            categories = ', '.join(self.CATEGORY_MAP.keys())
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""Analyze this receipt and extract:
1. The total amount spent (as a number only, no currency symbol)
2. The currency code (GBP, USD, EUR, etc.)
3. The category of expense - choose the MOST APPROPRIATE from: {categories}
   - If it's food or drink related but you can't clearly categorize it as Breakfast or Lunch, use "Dinner"
4. The date of the transaction (in YYYY-MM-DD format)

Respond ONLY with valid JSON in this exact format:
{{"amount": 12.50, "currency": "GBP", "category": "Lunch", "description": "Brief description", "date": "2024-09-30"}}"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            
            result_text = response.choices[0].message.content.strip()
            
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(result_text)
            result['currency'] = result.get('currency', 'GBP').upper()
            
            # Adjust date if too old
            if 'date' in result:
                adjusted_date, was_adjusted = self.adjust_date_if_too_old(result['date'])
                result['date'] = adjusted_date
                
                symbol = self.CURRENCY_SYMBOLS.get(result['currency'], result['currency'])
                date_display = f"{result.get('date', 'N/A')}"
                if was_adjusted:
                    date_display += " (adjusted)"
                print(f"✓ {symbol}{result['amount']} | {result['category']} | {date_display}")
            else:
                symbol = self.CURRENCY_SYMBOLS.get(result['currency'], result['currency'])
                print(f"✓ {symbol}{result['amount']} | {result['category']} | {result.get('date', 'N/A')}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error analyzing receipt: {e}")
            return None
    
    async def take_screenshot(self, name: str):
        """Take timestamped screenshot"""
        if not self.config.get('take_screenshots', True):
            return
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.config['screenshot_dir']}/{timestamp}_{name}.png"
        await self.page.screenshot(path=filename, full_page=True)
        return filename
    
    async def check_login(self):
        """Navigate to Kantata and verify SSO login"""
        print("\n🔐 Navigating to Kantata...")
        await self.page.goto(self.config['login_url'], wait_until='domcontentloaded')
        
        await self.page.wait_for_timeout(3000)
        
        if await self.page.locator('.slds-context-bar, .oneHeader').count() > 0:
            print("✓ Logged in via SSO")
            return
        
        print("\n⚠️  Please complete SSO login in the browser")
        print("   Waiting for login...")
        
        await self.page.wait_for_selector('.slds-context-bar, .oneHeader', timeout=60000)
        print("✓ Logged in")
    
    async def navigate_to_expenses(self):
        """Navigate to the expense claims section"""
        print("\n💰 Opening expense claims...")
        
        await self.page.get_by_role("button", name="Expense Claims List").click()
        print("  ✓ Opened list")
        
        await self.page.wait_for_timeout(1000)
        
        await self.page.get_by_role("menuitem", name="New Expense Claim").click()
        print("  ✓ Started new claim")
        
        await self.page.wait_for_timeout(2000)
    
    async def create_expense_claim_with_items(self, expenses: List[Dict], max_expenses: int = 15) -> str:
        """Create expense claim with multiple items (max 15 per Kantata limit)
        
        Returns:
            claim_name: The name of the created claim
        """
        claim_name = datetime.now().strftime("%B %-d %H:%M")
        expenses_to_add = expenses[:max_expenses]
        total_expenses = len(expenses_to_add)
        
        print(f"\n📝 Creating expense claim: {claim_name}")
        print(f"   Adding {total_expenses} expenses (max: {max_expenses})")
        
        project_id = expenses_to_add[0].get('project_id')
        category_id = expenses_to_add[0].get('category_id')
        
        iframe_locator = self.page.frame_locator('iframe[name^="vfFrameId_"]').last
        
        await iframe_locator.locator('input[name*="expenseClaimName"]').fill(claim_name)
        print(f"  ✓ Claim name: {claim_name}")
        
        await iframe_locator.get_by_role("combobox").select_option(project_id)
        print(f"  ✓ Project selected")
        
        await self.page.wait_for_timeout(1000)
        
        # Set incurred date to earliest date from all receipts
        dates_with_values = [exp.get('date') for exp in expenses_to_add if exp.get('date')]
        if dates_with_values:
            earliest_date = min(dates_with_values)
            from datetime import datetime as dt
            date_obj = dt.strptime(earliest_date, '%Y-%m-%d')
            incurred_date = date_obj.strftime('%d/%m/%Y')
            incurred_date_field = iframe_locator.locator('input[id*="incurredDateField"]')
            await incurred_date_field.fill(incurred_date)
            await incurred_date_field.press('Enter')
            print(f"  ✓ Incurred date: {incurred_date} (earliest)")
        
        await self.page.wait_for_timeout(1000)
        
        await iframe_locator.locator("#action-buttons span").nth(2).click()
        print("  ✓ Proceeding to items")
        
        await self.page.wait_for_timeout(1500)
        
        for i, expense in enumerate(expenses_to_add, 1):
            print(f"\n  [{i}/{total_expenses}] Adding expense...")
            
            await iframe_locator.get_by_text("Add Expense").nth(1).click()
            await self.page.wait_for_timeout(1000)
            
            expense_category_id = expense.get('category_id', category_id)
            await iframe_locator.locator(f'select[id*="expenseCategorySelect"]').nth(i-1).select_option(expense_category_id)
            print(f"    ✓ Category: {expense.get('category', 'Unknown')}")
            
            currency = expense.get('currency', 'GBP').upper()
            await iframe_locator.locator('select[name*="incurredAmountCurrencyField"]').nth(i-1).select_option(label=currency)
            print(f"    ✓ Currency: {currency}")
            
            amount = str(expense.get('amount', '0'))
            symbol = self.CURRENCY_SYMBOLS.get(currency, currency)
            await iframe_locator.locator('input[name*="incurredAmountField"]').nth(i-1).fill(amount)
            print(f"    ✓ Amount: {symbol}{amount}")
            
            if expense_date := expense.get('date'):
                from datetime import datetime as dt
                date_obj = dt.strptime(expense_date, '%Y-%m-%d')
                kantata_date = date_obj.strftime('%d/%m/%Y')
                date_field = iframe_locator.locator('input[id*="j_id219"]').nth(i-1)
                await date_field.fill(kantata_date)
                await date_field.press('Enter')
                print(f"    ✓ Date: {kantata_date}")
            
            await self.page.wait_for_timeout(500)
            
            # Check receipt box
            checkbox = iframe_locator.locator(f'input[id*="TheExpenseItems:{i-1}:"][id*="j_id331"]')
            await checkbox.check()
            print(f"    ✓ Receipt required")
            
            # Upload receipt
            if receipt_path := expense.get('receipt_path'):
                if receipt_path.exists():
                    add_button = iframe_locator.locator(f'a[onclick*="showFileUploadPopup(\'{i-1}\')"]')
                    await add_button.click()
                    await self.page.wait_for_timeout(2000)
                    
                    upload_frame = self.page.frame('fileUploadIFrame')
                    if not upload_frame:
                        upload_frame = next((f for f in self.page.frames if 'FileUpload' in f.url), None)
                    
                    if upload_frame:
                        await upload_frame.wait_for_selector('input[type="file"]', timeout=5000)
                        await upload_frame.locator('input[type="file"]').set_input_files(str(receipt_path.absolute()))
                        await self.page.wait_for_timeout(1000)
                        await upload_frame.locator('input[type="submit"][value="Upload"]').click()
                        await self.page.wait_for_timeout(2500)
                        print(f"    ✓ Uploaded: {receipt_path.name}")
            
            await self.page.wait_for_timeout(500)
        
        await self.take_screenshot('final_expense_report')
        
        # Click Save dropdown to reveal menu
        save_dropdown = iframe_locator.locator('.dd-btn.toolbar-button')
        await save_dropdown.click()
        await self.page.wait_for_timeout(500)
        
        # Click Save option from dropdown
        save_button = iframe_locator.locator('input[id*="TheForm:j_id137"]')
        await save_button.click()
        await self.page.wait_for_timeout(3000)
        
        print(f"\n✓ Saved: {claim_name} ({total_expenses} expenses)")
        return claim_name
    
    
    async def cleanup(self):
        """Close browser"""
        if self.context:
            await self.context.close()
    
    async def run(self):
        """Main execution method - process receipts with OpenAI"""
        try:
            print("=" * 60)
            print("🚀 Expensomatic Starting...")
            print("=" * 60)
            
            # Find receipt images
            receipts_dir = Path('receipts')
            if not receipts_dir.exists():
                print("\n❌ receipts/ folder not found")
                print("   Create it and add receipt images")
                return
            
            image_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.pdf']
            receipt_files = []
            for ext in image_extensions:
                receipt_files.extend(receipts_dir.glob(f'*{ext}'))
                receipt_files.extend(receipts_dir.glob(f'*{ext.upper()}'))
            
            if not receipt_files:
                print(f"\n❌ No receipts found in receipts/")
                print(f"   Add images: {', '.join(image_extensions)}")
                return
            
            # Sort receipts alphabetically by filename for consistent processing order
            receipt_files.sort(key=lambda p: p.name.lower())
            
            print(f"\n📸 Found {len(receipt_files)} receipt(s)")
            
            # Process in batches of 15
            total_receipts = len(receipt_files)
            num_batches = (total_receipts + 14) // 15  # Ceiling division
            
            if num_batches > 1:
                print(f"   Will create {num_batches} expense claims (15 receipts each)")
            
            print("=" * 60)
            
            # Create failed folder for receipts that can't be analyzed
            failed_dir = receipts_dir / 'failed'
            failed_dir.mkdir(exist_ok=True)
            failed_receipts = []
            
            # Open browser once at the start
            print("\n" + "=" * 60)
            print("🌐 Opening browser...")
            print("=" * 60)
            await self.init_browser()
            await self.check_login()
            
            batches_submitted = 0
            
            # Process each batch: analyze then submit immediately
            for batch_num in range(num_batches):
                start_idx = batch_num * 15
                end_idx = min(start_idx + 15, total_receipts)
                batch_receipts = receipt_files[start_idx:end_idx]
                
                print(f"\n{'=' * 60}")
                print(f"📦 BATCH {batch_num + 1}/{num_batches} - Analyzing {len(batch_receipts)} receipts")
                print("=" * 60)
                
                expenses = []
                for i, receipt_path in enumerate(batch_receipts, 1):
                    print(f"\n[{i}/{len(batch_receipts)}] {receipt_path.name}")
                    
                    result = self.analyze_receipt_with_openai(str(receipt_path))
                    
                    if result:
                        category_name = result.get('category', 'Other')
                        category_id = self.CATEGORY_MAP.get(category_name, self.CATEGORY_MAP['Other'])
                        
                        expenses.append({
                            'amount': result['amount'],
                            'currency': result.get('currency', 'GBP'),
                            'category': category_name,
                            'description': result.get('description', receipt_path.stem),
                            'date': result.get('date'),
                            'receipt_path': receipt_path,
                            'project_id': self.config['project_id'],
                            'category_id': category_id,
                        })
                    else:
                        print(f"   ⚠️  Analysis failed - moving to failed/")
                        # Move failed receipt to failed folder
                        try:
                            failed_path = failed_dir / receipt_path.name
                            receipt_path.rename(failed_path)
                            failed_receipts.append(receipt_path.name)
                            print(f"   ✓ Moved to: failed/{receipt_path.name}")
                        except Exception as e:
                            print(f"   ❌ Could not move file: {e}")
                
                if not expenses:
                    print(f"\n⚠️  No valid expenses in this batch, skipping submission")
                    continue
                
                # Submit this batch immediately
                print(f"\n✓ Analyzed {len(expenses)} expenses")
                print(f"\n{'=' * 60}")
                print(f"📋 BATCH {batch_num + 1}/{num_batches} - Creating claim")
                print("=" * 60)
                for i, exp in enumerate(expenses, 1):
                    symbol = self.CURRENCY_SYMBOLS.get(exp.get('currency', 'GBP'), exp.get('currency', 'GBP'))
                    print(f"{i:2d}. {exp['description'][:45]:45s} {symbol}{exp['amount']:7.2f}")
                print("=" * 60)
                
                await self.navigate_to_expenses()
                claim_name = await self.create_expense_claim_with_items(expenses, max_expenses=15)
                
                # Create subfolder and move receipts
                claim_folder = receipts_dir / claim_name.replace(':', '-')  # Replace : for filesystem
                claim_folder.mkdir(exist_ok=True)
                
                print(f"\n📁 Moving receipts to: {claim_folder.name}/")
                for expense in expenses:
                    receipt_path = expense['receipt_path']
                    new_path = claim_folder / receipt_path.name
                    receipt_path.rename(new_path)
                    print(f"   ✓ Moved: {receipt_path.name}")
                
                batches_submitted += 1
                print(f"\n✓ Batch {batch_num + 1} completed!")
                
                # Manual confirmation before proceeding to next batch
                if batch_num + 1 < num_batches:  # Don't prompt after the last batch
                    print("\n" + "=" * 60)
                    print("⏸️  MANUAL CONFIRMATION REQUIRED")
                    print("=" * 60)
                    print(f"Please verify that Batch {batch_num + 1} was saved successfully in the browser.")
                    print(f"Remaining: {num_batches - (batch_num + 1)} batch(es)")
                    print("\nPress Enter to continue to the next batch, or Ctrl+C to stop...")
                    input()
                    print("✓ Continuing to next batch...\n")
            
            if batches_submitted == 0:
                print("\n❌ No batches were submitted (all receipts failed analysis)")
                return
            
            print("\n" + "=" * 60)
            print(f"✓ All batches completed! ({batches_submitted} submitted)")
            if failed_receipts:
                print(f"\n⚠️  {len(failed_receipts)} receipt(s) failed analysis and were moved to failed/:")
                for failed_name in failed_receipts:
                    print(f"   - {failed_name}")
            print("=" * 60)
            
            print("\nBrowser open for 30s...")
            await self.page.wait_for_timeout(30000)
            
        except Exception as e:
            print(f"\n❌ Error occurred: {str(e)}")
            raise
        finally:
            await self.cleanup()


async def main():
    """Main entry point"""
    automation = Expensomatic()
    await automation.run()


if __name__ == "__main__":
    asyncio.run(main())
