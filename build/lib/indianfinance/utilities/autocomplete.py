import json
import requests



def autocomplete(company_symbol):
    
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:80.0) Gecko/20100101 Firefox/80.0'}
    url_host = "https://www.nseindia.com/"
    url_autocomplete = "https://www.nseindia.com/api/search/autocomplete?q="
    
    with requests.session() as s:

        # load cookies:
        s.get(url_host, headers=headers)
    
        autocomplete_data = s.get(url_autocomplete + company_symbol, headers=headers).json()
        print("Couldn't find the symbol: ", company_symbol)
        print("================= Did you mean these ================")
        for name in autocomplete_data["symbols"]:
            print("Symbol: {}, Company name: {}".format(name['symbol'], name['symbol_info']))