# Amazon Order Data Request Guide

This directory contains documentation for requesting and processing your complete Amazon order history using Amazon's official data request feature.

## 📁 Files in This Directory

- **`amazon_data_request_guide.md`** - Complete step-by-step guide for requesting your data from Amazon
- **`README.md`** - This overview file
- **`extract_amazon_data.sh`** - Helper script for automated extraction
- **`data/`** - Directory containing extracted Amazon order data (date-stamped subdirectories)

## 🚀 Quick Start

### Step 1: Request Your Data (5 minutes)

1. **Navigate to Amazon Privacy Central:**
   - Go to: https://www.amazon.com/hz/privacy-central/data-requests/preview.html
   - Or: Amazon.com → Account & Lists → Your Account → Request Your Information

2. **Submit Data Request:**
   - Click "Request your data"
   - Select "Your Orders" category
   - Click "Submit Request"
   - You'll receive a confirmation email immediately

3. **Wait for Processing:**
   - Amazon will process your request (typically 4-5 hours)
   - You'll receive an email when your data is ready
   - The email contains a link to download your data

### Step 2: Download and Extract (5 minutes)

1. **Download the ZIP file:**
   - Click the link in Amazon's email
   - Download `Your Orders.zip` to `amazon/data/`

2. **Extract to date-stamped directory with account name:**
   
   **Option A: Using the helper script (recommended):**
   ```bash
   # Navigate to the repository root
   cd /path/to/finances
   
   # Run the extraction helper script
   ./amazon/extract_amazon_data.sh "Your Orders.zip" karl
   ./amazon/extract_amazon_data.sh "Your Orders Erica.zip" erica
   ```
   
   **Option B: Manual extraction:**
   ```bash
   cd amazon/data/
   # Replace YYYY-MM-DD with today's date and accountname with the account owner's name
   mkdir YYYY-MM-DD_accountname_amazon_data
   unzip "Your Orders.zip" -d YYYY-MM-DD_accountname_amazon_data/
   rm "Your Orders.zip"  # Optional: remove ZIP after extraction
   ```
   
   **Example for multiple accounts:**
   ```bash
   # For Karl's account
   mkdir 2025-08-24_karl_amazon_data
   unzip "Your Orders Karl.zip" -d 2025-08-24_karl_amazon_data/
   
   # For Erica's account
   mkdir 2025-08-24_erica_amazon_data
   unzip "Your Orders Erica.zip" -d 2025-08-24_erica_amazon_data/
   ```

## 👥 Multi-Account Support

### Directory Naming Convention

When extracting Amazon data for multiple accounts, use the following naming convention:
- Format: `YYYY-MM-DD_accountname_amazon_data`
- Example: `2025-08-24_karl_amazon_data`, `2025-08-24_erica_amazon_data`

### How It Works

1. **Separate Data Exports**: Each Amazon account requires its own data export request
2. **Account Identification**: The account name in the directory identifies the data source
3. **Automatic Discovery**: Transaction matching tools automatically find all account directories
4. **Combined Searching**: Tools search across all accounts to find matches

### Managing Multiple Accounts

- Export dates don't need to match exactly between accounts
- Tools will use the most recent export for each account
- Specify accounts to search with `--accounts` parameter (e.g., `--accounts karl erica`)
- Without `--accounts`, all available accounts are searched

## 📊 Data Structure

### Files Included in Export

The ZIP file contains comprehensive order data in CSV format:

- **`Retail.OrderHistory.1/`** - Main retail order history (most important)
  - `Retail.OrderHistory.1.csv` - Complete purchase history
  
- **`Digital-Ordering.1/`** - Digital purchases
  - `Digital Orders.csv` - Digital content orders
  - `Digital Items.csv` - Individual digital items
  - `Digital Orders Monetary.csv` - Payment details
  
- **`Retail.CustomerReturns.1/`** - Return history
- **`Retail.OrdersReturned.1/`** - Returned orders details
- **Additional directories** for specific order types and payment methods

### Key Data Fields

The main `Retail.OrderHistory.1.csv` includes:
- Order ID
- Order Date
- Order Status
- Product Name
- Product Category
- ASIN/ISBN
- Quantity
- Purchase Price Per Unit
- Total Amount
- Payment Method
- Shipping Address
- And many more fields...

## 📈 Benefits of This Approach

### Compared to Manual Extraction

| Aspect | Manual Browser Extraction | Official Data Request |
|--------|---------------------------|----------------------|
| Time Investment | 4-6 hours active work | 5 minutes + 4-5 hour wait |
| Completeness | ~95% (human errors) | 100% complete |
| Format | Manual YAML creation | Structured CSV files |
| Reliability | Depends on page changes | Official API, stable |
| Historical Data | Limited by UI | Complete history |
| Automation Potential | None | Full CSV processing |

### Use Cases

- **Transaction Categorization**: Reference for YNAB transaction matching
- **Spending Analysis**: Complete purchase history analysis
- **Tax Preparation**: Business expense identification
- **Warranty Tracking**: Product purchase dates and details
- **Return Management**: Track return windows and history

## ⏰ Processing Timeline

1. **Request**: 2-3 minutes
2. **Amazon Processing**: 4-5 hours (varies by account size)
3. **Download**: 1-2 minutes
4. **Extraction**: 1-2 minutes
5. **Total Time**: ~5 hours (mostly waiting)

## 🔄 Regular Updates

### Recommended Schedule
- **Quarterly**: For active Amazon users
- **Semi-annually**: For moderate users
- **Annually**: For light users or tax preparation

### Update Process
1. Request new data export for each account
2. Extract to new date-stamped directory with account name
3. Keep previous exports for comparison
4. Process new data as needed

**Multi-account example:**
```bash
# Update Karl's data
mv 2025-08-24_karl_amazon_data 2025-08-24_karl_amazon_data.old
mkdir 2025-11-24_karl_amazon_data
unzip "Your Orders Karl.zip" -d 2025-11-24_karl_amazon_data/

# Update Erica's data
mv 2025-08-24_erica_amazon_data 2025-08-24_erica_amazon_data.old
mkdir 2025-11-24_erica_amazon_data
unzip "Your Orders Erica.zip" -d 2025-11-24_erica_amazon_data/
```

## 📝 Data Processing Tips

### CSV Processing
- Use Python pandas, Excel, or any CSV tool
- Sort by date for chronological analysis
- Filter by category for spending analysis
- Join with YNAB exports for reconciliation

### Storage Best Practices
- Keep exports in date-stamped directories
- Archive older exports after processing
- Never commit raw data to version control
- Consider encrypting sensitive financial data

## ⚠️ Important Notes

### Privacy & Security
- Data contains sensitive purchase history
- Keep files secure and encrypted
- Don't share or commit to public repositories
- Delete files when no longer needed

### Data Limitations
- Historical data depends on account age
- Some very old orders may have limited details
- Third-party marketplace items may have less info
- Gift orders show limited recipient information

## 🆘 Troubleshooting

### Common Issues

**Request not received:**
- Check spam/promotions folder
- Verify email address on account
- Try requesting again after 24 hours

**Download link expired:**
- Links typically valid for 7 days
- Request data again if expired

**Missing data:**
- Some categories require separate requests
- Check all CSV files in the export
- Very old orders may have limited data

**Large file size:**
- Long-term users may have large exports
- Extract in stages if needed
- Use command-line tools for large files

## 📚 Next Steps

After extracting your data:
1. Review the CSV files to understand your purchase patterns
2. Create scripts to process and analyze the data
3. Use for YNAB transaction categorization reference
4. Build spending reports and visualizations

---

**Questions?** The complete guide is in `amazon_data_request_guide.md`