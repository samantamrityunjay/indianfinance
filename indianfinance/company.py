import json
import requests
import os
from zipfile import ZipFile
from datetime import datetime
from .utilities import create_dir, autocomplete




class company:
    def __init__(self, company_symbols):
        
        company_symbols_list = company_symbols.split()
        self.company_symbols_list = company_symbols_list
        self.headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:80.0) Gecko/20100101 Firefox/80.0'}
        self.url_host = "https://www.nseindia.com/"
        self.url_api_marketinfo = "https://www.nseindia.com/api/quote-equity?symbol="
        self.url_api_annualreport = "https://www.nseindia.com/api/annual-reports?index=equities&symbol="
        self.url_api_historical = "https://www.nseindia.com/api/historical/cm/equity?symbol={}&series=[%22EQ%22]&from={}&to={}"
        
        with requests.session() as s:
            
            # load cookies:
            s.get(self.url_host, headers = self.headers)
                
            for company_symbol in company_symbols_list:                      
                
                # get data:
                json_data = s.get(self.url_api_annualreport + company_symbol, headers = self.headers).json()
                
                if json_data['data']:
                    pass
                else:
                    autocomplete(company_symbol)
                    raise ValueError
     
    def market_info(self):
        companyinfo = {} 
         
        with requests.session() as s:
            
            # load cookies:
            s.get(self.url_host, headers = self.headers)
            
            for company_symbol in self.company_symbols_list:
                companyinfo[company_symbol] = {}
                json_data = s.get(self.url_api_marketinfo + company_symbol, headers = self.headers).json()
                companyinfo[company_symbol]["FullName"] = json_data["info"]["companyName"]
                companyinfo[company_symbol]["Industry"] = json_data["metadata"]["industry"]
                companyinfo[company_symbol]["ISIN"] = json_data["metadata"]["isin"]
                companyinfo[company_symbol]["LastPrice"] = json_data["priceInfo"]["lastPrice"]
                companyinfo[company_symbol]["MCap"] = json_data["securityInfo"]["issuedCap"] * json_data["priceInfo"]["lastPrice"] / 1e12
        
        return json.dumps(companyinfo) 
    
    
    def historical_data(self, from_date, to_date):
        
        historical_info = {} 
        from_date =  datetime.strptime(from_date,"%d%m%Y").strftime("%d-%m-%Y")
        to_date =  datetime.strptime(to_date,"%d%m%Y").strftime("%d-%m-%Y")
        
        with requests.session() as s:
            
            # load cookies:
            s.get(self.url_host, headers = self.headers)
            
            for company_symbol in self.company_symbols_list:
                historical_info[company_symbol] = {"Date":[], "Open":[], "Close":[], "High":[], "Low":[]}
                json_data = s.get(self.url_api_historical.format(company_symbol, from_date, to_date), headers = self.headers).json()
                for dictionary in json_data["data"]:
                    historical_info[company_symbol]["Date"].append(dictionary["CH_TIMESTAMP"])
                    historical_info[company_symbol]["Open"].append(dictionary["CH_OPENING_PRICE"])
                    historical_info[company_symbol]["Close"].append(dictionary["CH_CLOSING_PRICE"])
                    historical_info[company_symbol]["High"].append(dictionary["CH_TRADE_HIGH_PRICE"])
                    historical_info[company_symbol]["Low"].append(dictionary["CH_TRADE_LOW_PRICE"])
                    
        return json.dumps(historical_info)        
                    
    def annual_report(self, years):
        
        ROOT_DIR = os.path.join(os.getcwd(), 'AnnualReport')
        ZIP_DIR = os.path.join(ROOT_DIR, 'ZipFiles')
        PDF_DIR = os.path.join(ROOT_DIR, 'PDFFiles')
        

        create_dir(ROOT_DIR)
        create_dir(ZIP_DIR)
        create_dir(PDF_DIR)
               
        
        years = years.split()  


        with requests.session() as s:
            
            # load cookies:
            s.get(self.url_host, headers = self.headers)
            
            for company_symbol in self.company_symbols_list:
                COMPANY_ZIP_DIR = os.path.join(ZIP_DIR, company_symbol)
                COMPANY_PDF_DIR = os.path.join(PDF_DIR, company_symbol)
                
                create_dir(COMPANY_ZIP_DIR)
                create_dir(COMPANY_PDF_DIR)
                    
                # get data:
                json_data = s.get(self.url_api_annualreport + company_symbol, headers = self.headers).json()
                
                               
                    
                for year in years:
                    zip_file_path = os.path.join(COMPANY_ZIP_DIR, year+".zip")
                    pdf_file_path = os.path.join(COMPANY_PDF_DIR, year+".pdf")
                    
                    if os.path.exists(pdf_file_path):
                        print("File already there for {}!".format(year))
                    
                    else:
                        for year_wise_data in json_data['data']:
                            if year_wise_data['toYr'] == year:
                                download_file_path = year_wise_data['fileName']
                                print(".......... Downloading {} ZIP folder from year {} ..........".format(company_symbol, year))
                                r = requests.get(download_file_path, allow_redirects=True)
                                open(zip_file_path, 'wb').write(r.content)
                                
                                print(".......... Unzipping {} Annual Report from year {} ..........".format(company_symbol, year))
                                with ZipFile(zip_file_path) as zf:
                                    for filename in zf.namelist():
                                        if filename.startswith("AR"):
                                            with open(pdf_file_path, "wb") as f:  
                                                f.write(zf.read(filename))
                                
                                
                                break
            
       
        
    

