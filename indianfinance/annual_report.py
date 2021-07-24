import json
import requests
import os
from zipfile import ZipFile

from .utilities.create_dir import create_dir


def annual_report():
    
    ROOT_DIR = os.path.join(os.getcwd(), 'AnnualReport')
    ZIP_DIR = os.path.join(ROOT_DIR, 'ZipFiles')
    PDF_DIR = os.path.join(ROOT_DIR, 'PDFFiles')
    # RESULT_DIR = os.path.join(os.getcwd(), 'results')
    # OUTPUT_DIR = os.path.join(os.getcwd(), 'outputs')



    create_dir(ROOT_DIR)
    create_dir(ZIP_DIR)
    create_dir(PDF_DIR)


    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:80.0) Gecko/20100101 Firefox/80.0'}
    url_host = 'https://www.nseindia.com/'
    url_api = 'https://www.nseindia.com/api/annual-reports?index=equities&symbol='
    url_autocomplete = "https://www.nseindia.com/api/search/autocomplete?q="

    company_symbol = input("Enter the company symbol: ")
    years = input("Enter the years to download from: ").split()

    COMPANY_ZIP_DIR = os.path.join(ZIP_DIR, company_symbol)
    COMPANY_PDF_DIR = os.path.join(PDF_DIR, company_symbol)


    with requests.session() as s:

        # load cookies:
        s.get(url_host, headers=headers)
        
        # get data:
        json_data = s.get(url_api+company_symbol, headers=headers).json()
        
        if json_data['data']:
            create_dir(COMPANY_ZIP_DIR)
            create_dir(COMPANY_PDF_DIR)
                
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
        
        else:
            autocomplete_data = s.get(url_autocomplete+company_symbol, headers=headers).json()
            print("================= Did you mean these ================")
            for name in autocomplete_data["symbols"]:
                print("Symbol: {}, Company name: {}".format(name['symbol'], name['symbol_info']))
            # print(json.dumps(autocomplete_data, indent=4))
            
                        

        
        
        
        # print(data)
        # download = data['data'][0]['fileName']
        # r = requests.get(download, allow_redirects=True)
        # open('SBIN.zip', 'wb').write(r.content)

        # print data to screen:
        # print(json.dumps(data, indent=4))
        
    

