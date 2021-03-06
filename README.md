# indianfinance
Get real-time information about companies listed in indian stock market.
## Table of Contents
- [Installation](#installation)
- [Methods](#methods)
- [Basic Examples](#basic-examples)
- [Acknowledgements](#acknowledgements)

## Installation
``` pip install indianfinance ```

## Methods
To start getting data from companies, call `company(x)` where `x` can be
- A company symbol like `INFY` (for Infosys Limited)
- A list of company symbols separated by space like `INFY WIPRO TECHM` (For Infosys Limited, Wipro and Tech Mahindra)

`company` is the class and there are currenty three methods attached with it:
- `market_info()` - gives general information about the company and data is presented in the foem of json with the following fields :
    - `FullName`: Full Name of the company incorporated in the stock market
    - `Industry` - industry it belongs to 
    - `ISIN` - mentions the International Securities Identification Number
    - `LastPrice` - the last pice the company share was traded at in indian rupees
    - `MCap` - the total free float market capitalization of the company (in lakh crores)


- `historical_data(fromDate, toDate)`: presents the historical data of share market from `fromDate` to `toDate`. The date format for the input are `DDMMYYYY`.
The json data returned contained following fields:
    - `Date`
    - `Open` - opening price 
    - `Close` - closing price
    - `High` - intraday highest price
    - `Low` - intraday lowest price

- `annual_report(years)`: this method downloads the annual report for the companies for the years mentioned. the years must be separated with space (ex: `2021 2020`). This method creates a directory `AnnualReport` in the current directory. Following is the tree structure.
```
AnnualReport
|
|--- PDFFiles 
|    |
|    |--Company1
|    |   |
|    |   |-year1.pdf
|    |   |-year2.pdf
|    |     -------
|    |--Company2
|        |
|        |-year1.pdf
|        |-year2.pdf
|          -------
|--- ZipFiles (----> annual reports are in  
|    |            zipfiles and extracted to 
|    |             PDF folder)
|    |
|    |--Company1
|    |   |
|    |   |-year1.zip
|    |   |-year2.zip
|    |     -------
|    |--Company2
|        |
|        |-year1.zip
|        |-year2.zip
|          -------
```
## Basic Examples
```
import indianfinance

>>> c = indianfinance.company("WIPRO")

>>>> print(c.market_info())

{"WIPRO": {"FullName": "Wipro Limited", "Industry": "COMPUTERS - SOFTWARE", "ISIN": "INE075A01022", "LastPrice": 599.55, "MCap": 3.285}

>>> print(c.historical_data("04082021", "06082021"))

{"WIPRO": {"Date": ["2021-08-06", "2021-08-05", "2021-08-04"], "Open": [603.75, 597.5, 603.5], "Close": [598, 600.9, 596.8], "High": [606.4, 614.5, 604], "Low": [596.3, 597.5, 594.3]}}

```
Wrong company symbol will give error but at the same time give closest symbols also

```
>>> import indianfinance
>>> c = indianfinance.company("AIRTEL")

Couldn't find the symbol:  AIRTEL
============ Did you mean these ==============
Symbol: BHARTIARTL, Company name: Bharti Airtel Limited (----> gives the most relevant company symbol)
Traceback (most recent call last):
    line 10, in <module>
    c = indianfinance.company("AIRTEL")
  File "\indianfinance\indianfinance\company.py", line 36, in __init__
    raise ValueError
ValueError
```

## Acknowlegements
The following package has been only possible due to the APIs of [NSE](https://www.nseindia.com/)