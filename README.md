# Redfin Scraper

A data extraction and processing tool for Redfin real estate listings that transforms raw listing data into structured, analysis-ready formats.

## Overview

This project demonstrates my ability to work with external data sources, process complex JSON structures, and transform unstructured data into a normalized format for analysis. The Redfin Scraper automates the extraction of real estate listing details from Redfin and converts them into a well-organized CSV format suitable for market analysis or investment opportunity evaluation.

## Features

- Extracts comprehensive property details from Redfin listings
- Processes complex nested JSON structures into a flat, normalized format
- Intelligently maps property types and infers additional metadata
- Performs automated parsing of listing descriptions to extract key property attributes
- Outputs a structured CSV formatted for real estate analysis

## Technical Implementation

### Data Processing Pipeline

1. **Data Collection**: Raw JSON data is collected from Redfin listings using Apify web scraping platform
2. **Data Transformation**: The `apify-json-to-deal-csv.py` script processes the raw JSON data
3. **Data Normalization**: Property attributes are standardized and normalized
4. **Output Generation**: Structured data is saved to CSV for further analysis

### Key Technical Components

- **Property Type Mapping**: Converts Redfin internal property type codes to human-readable categories
- **Unit Count Inference**: Uses regex pattern matching on listing descriptions to determine multi-unit properties
- **Address Normalization**: Standardizes address formats for consistency
- **Parking Detection**: Employs heuristic methods to identify parking features from unstructured text

## Usage

```bash
# Clone the repository
git clone https://github.com/yourusername/redfin-scraper.git
cd redfin-scraper

# Install required packages
pip install pandas

# Run the data processing script
python apify-json-to-deal-csv.py

# Output will be generated as quick_deal_import.csv
```

## Dependencies

- Python 3.6+
- pandas
- json
- re