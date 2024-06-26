from ssl import SSLError
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates # To generate front end for the FastAPI backend 
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, validator # To validate user request 
from pydantic.networks import EmailStr, AnyHttpUrl # To validate email and URL in specific user input fields
import re
from os import getcwd, remove
import random
import string
import shutil
import fileinput
import sys
import pdfkit
from bs4 import BeautifulSoup # To check if a user input is HTML
from  urlextract import URLExtract # To extract URLs from user input 
import tldextract # To extract domains from URLs in user input 
from ipaddress import IPv4Address # To validate if a user input has specific IP address
from socket import gethostbyname, gaierror # To resolve domains in user input
import requests # To check HTTP redirection on URLs in user input
from bleach import clean # To sanitize the HTML input from the user
from urllib3.exceptions import NewConnectionError
from urllib.parse import urlparse

app = FastAPI()

templates = Jinja2Templates(directory="templates")

class Item(BaseModel):
    name: str
    job: str
    email: EmailStr
    portfolio: AnyHttpUrl
    phone: str
    twitter: str

    @validator("phone")
    def phone_validation(cls, v):
    # logger.debug(f"phone in 2 validator:{v}")ter
        regex = r"^(\+)[1-9][0-9\-\(\)\.]{9,15}$"
        if v and not re.search(regex, v, re.I):
            raise ValueError("Phone Number Invalid.")
        return v

    class Config:
        orm_mode = True
        use_enum_values = True

@app.get("/", response_class=HTMLResponse)
async def form(request: "Request"):
    context={'request': request}
    return templates.TemplateResponse("create_card.html", context)

@app.post("/create-card", response_class=FileResponse)
async def create_card(card: Item, request: "Request", background_tasks: BackgroundTasks):
    context={'request': request}
    ## Generating unique ID to append to final business card. This is to ensure every user has unique file.
    print(card)
    if bool(BeautifulSoup(card.twitter, "html.parser").find()):
        print("HTML Detected")
        #ssrf_blacklist(card.twitter)

    unique_id = ''.join(random.choices(string.ascii_lowercase, k=15))
    final_business_card_html_file = "business-card-final-"+unique_id+".html"
    final_business_card_pdf_file = "business-card-final-"+unique_id+".pdf"

    shutil.copyfile("business-card-template.html", final_business_card_html_file)
    
    def replaceAll(file,searchExp,replaceExp):
        for line in fileinput.input(file, inplace=1):
            if searchExp in line:
                line = line.replace(searchExp,replaceExp)
            sys.stdout.write(line)

    replaceAll(final_business_card_html_file,'PERSON_NAME',clean(card.name))
    replaceAll(final_business_card_html_file,'PERSON_JOB', clean(card.job))
    replaceAll(final_business_card_html_file,'EMAIL_ADDRESS', clean(card.email))
    replaceAll(final_business_card_html_file,'PORTFOLIO', clean(card.portfolio))
    replaceAll(final_business_card_html_file,'MOBILE_NUMBER', clean(card.phone))
    replaceAll(final_business_card_html_file,'TWITTER_HANDLE', card.twitter)

    # Create a background task to delete PDF and HTML files

    try:
        print("Awesome PDF printing!!")
        options = {"enable-local-file-access": None}
        pdfkit.from_file(getcwd()+"/"+final_business_card_html_file,
        getcwd()+"/"+final_business_card_pdf_file, options=options)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=400, detail="There is an issue with the input. PDF Generation failed")
    #save_pdf(final_business_card_pdf_file, "file://"+getcwd()+"/"+final_business_card_html_file)
    
    headers = {'Content-Disposition': 'attachment; filename="business-card.pdf"'}
    #return Response(final_business_card_pdf_file, headers=headers, media_type='application/pdf')
    background_tasks.add_task(delete_files, final_business_card_html_file, final_business_card_pdf_file)
    return FileResponse(final_business_card_pdf_file, media_type="application/pdf", headers={
             'Content-Disposition': 'inline;filename="business-card.pdf"' })

def delete_files(html_file, pdf_file):
    print("Running background tasks!!")
    remove(html_file)
    remove(pdf_file)

def ssrf_blacklist(user_input):

    black_list = ["XMLHttpRequest","dict:","dict","jar:","passwd","169.254.169.254","file","dict","sftp","tftp","ldap","gopher","netdoc","file://","dict://","sftp://","tftp://","ldap://","gopher://","netdoc://"]
    for black_list_item in black_list:
        if black_list_item in user_input:
            raise HTTPException(status_code=400, detail="Malicious activity Detected!!")
            #return {"Error": "Malicious IP Detected!!"}
    else:
        extractor = URLExtract()
        urls_in_payload = extractor.find_urls(user_input, only_unique=True,check_dns=True)
        print("URLs before", urls_in_payload)

        ipPattern = re.compile("(?:(?:1\d\d|2[0-5][0-5]|2[0-4]\d|0?[1-9]\d|0?0?\d)\.){3}(?:1\d\d|2[0-5][0-5]|2[0-4]\d|0?[1-9]\d|0?0?\d)")
        ip_addresses_in_payload = []
        for url in urls_in_payload:
            print("url is " + url)
            ip = re.findall(ipPattern,url)
            if ip:
                for i in ip:
                    ip_addresses_in_payload.append(i)
                    #urls_in_payload.remove(url)
        print(ip_addresses_in_payload)

        ## Check if IP Addresses match 169.254.169.254
        for ip in ip_addresses_in_payload:
            try:
                urls_in_payload.remove(ip)
                if IPv4Address("169.254.169.254") == IPv4Address(ip):
                    raise HTTPException(status_code=400, detail="Malicious IP Detected!!")
            except ValueError as e:
                pass

        print("URLs after", urls_in_payload)

        ## Extract and remove any I
        # P addresses
        domains_in_payload =  []
        for url in urls_in_payload:
            ext = tldextract.extract(url)
            domains_in_payload.append('.'.join(part for part in ext if part))
        print(domains_in_payload)

        ## Resolve domains and check if they point to 169.254.169.254
        try:
            for domain in domains_in_payload:
                #print("Domain is ", domain)
                a_record = gethostbyname(domain)
                print("A Record is ", a_record)
                if IPv4Address("169.254.169.254") == IPv4Address(a_record):
                    #print("Dangerous resolution")
                    raise HTTPException(status_code=400, detail="Malicious Resolution Detected!!")
        except gaierror as e:
            print(e)

        ipPattern = re.compile("(?:(?:1\d\d|2[0-5][0-5]|2[0-4]\d|0?[1-9]\d|0?0?\d)\.){3}(?:1\d\d|2[0-5][0-5]|2[0-4]\d|0?[1-9]\d|0?0?\d)")
        
        ## Check if domains have 302/301 resolution
        for url in urls_in_payload:
            print("URL before urlpase is", url)
            url = urlparse(url).netloc
            print("URL after urlpase is", url)

            try:
                # <iframe src=http://18.237.130.95:5000>
                print("Checking HTTP redirection")
                http_response = requests.get("http://"+url,  allow_redirects=False)
                print(http_response.request.url)
                print(http_response.status_code)
                #print(http_response)
                if http_response.status_code == 301 or http_response.status_code == 302 or http_response.status_code == 304 or http_response.status_code in range(500, 600):
                    print("Bad redirection")
                    raise HTTPException(status_code=400, detail="Malicious Redirection Detected!!")
                else:
                    pass

                if re.findall(ipPattern,url):
                    pass
                else:
                    print("Checking HTTPS redirection")
                    print(http_response.status_code)
                    https_response = requests.get("https://"+url,  allow_redirects=False)
                    if https_response.status_code == 301 or https_response.status_code == 302 or https_response.status_code == 304 or https_response.status_code in range(500, 600):
                        raise HTTPException(status_code=400, detail="Malicious Redirection Detected!!")
                    else:
                        pass
            except requests.exceptions.SSLError as e:
                        print(e)
                        raise HTTPException(status_code=400, detail="Something went wrong with the SSL") 
            except SSLError as e:
                        print(e)
                        raise HTTPException(status_code=400, detail="Something went wrong with the SSL")
            except ConnectionError as e:
                        print(e)
                        raise HTTPException(status_code=400, detail="Something went wrong when server was making a connection")
            except NewConnectionError as e:
                        print(e)
                        raise HTTPException(status_code=400, detail="Something went wrong when server was making a new connection")
