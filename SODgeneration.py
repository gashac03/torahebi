import streamlit as st
from datetime import date
import requests
from bs4 import BeautifulSoup
from docxtpl import DocxTemplate
import re
from io import BytesIO
import io, zipfile



LOGIN_URL = ('https://www.torahebi.jp/admin/login/')
VALID_EMAIL = "test@example.com"
VALID_PASSWORD = "1234"
translation_table = str.maketrans("", "", ",円")
found_links = []


searchResultURL_Preflex = ('https://www.torahebi.jp/admin/order/?mode=search&s_name=&s_id=&s_from=')
searchResultURL_Suflex = ('&s_payment_id=&s_status_id=')

class OrderSummary:
    def __init__(self, orderSubTotal, orderdeliveryFee, orderTransFee, orderTotal):
        
        self.subtotal = orderSubTotal
        self.deliveryFee = orderdeliveryFee
        self.transFee = orderTransFee
        self.total = orderTotal

class OrderItem:
    def __init__(self, orderID, orderName, orderPrice, orderQuantity):
        self.size = checkItemSize(orderName)
        self.id = orderID
        self.name = orderName        
        self.price = orderPrice
        self.quan = orderQuantity
        self.amount = f"{int(orderPrice.translate(translation_table))*int(orderQuantity):,}" + "円"

def checkItemSize(itemName):
    itemSize = ""
    if "200g" in itemName or "100g×2" in itemName:
        itemSize = "200g"
    elif "Drip Bag" in itemName or "TROPICAL BLEND" in itemName :
        itemSize = "12g x 10"
    elif "Variety Pack" in itemName or "虎蛇林檎" in itemName :
        itemSize = "12g x 5"

    return itemSize 

def checkCredential(email, password):
    status = False
    payload = {

    'mailaddress' : email,
    'password' : password
    }  
    with requests.session() as session:
        s = session.post(LOGIN_URL, data=payload)
        soup = BeautifulSoup(s.text,'html.parser')
        errorMsgs = soup.find("p", class_="error form_error_txt")
        if errorMsgs == None:
            status = True

    return status

def extract_OrderLink(s):
    
    soup = BeautifulSoup(s.text,'html.parser')
    link_table = soup.find("table", class_="list order")
    
    link_rows = link_table.find_all('tr')[1:]
    for link_row in link_rows:
        cols = link_row.find_all("td")
        #Only get the link of the delivered order
        if cols[5].get_text(strip=True) == "発送済" :
            
            a_tag = cols[0].find("a")
            href = a_tag["href"]
            #print(href)
            found_links.append(href)
    

    return 

def getPages(s):
    soup = BeautifulSoup(s.text,'html.parser')
    pattern = re.compile(r"^https://www\.torahebi\.jp/admin/order/\?page=")
    page_table =  [a["href"] for a in soup.find_all("a", href=pattern)]
    if len(page_table)>1:
        page_table.pop()
    return page_table

def extract_CustomerName(rTxt):
    custName =""
    orderNum = ""
    tableSoup = BeautifulSoup(rTxt,'html.parser')
    for tr in tableSoup.find_all('tr'):
            th = tr.find("th")
            td = tr.find("td")
            if th and th.get_text(strip=True) == "名前:":
                if custName == "":
                    custName = td.get_text(strip=True)
            if th and th.get_text(strip=True) == "注文番号:":
                if orderNum == "":
                    orderNum = td.get_text(strip=True)
                    #print(orderNum)   
    return orderNum, custName

def extract_OrderSummary(rTxt):
    orderSummaryList = []
    
    subTotal =""
    deliveryFee = ""
    transactionFee =""
    totalFee =""

    tableSoup = BeautifulSoup(rTxt,'html.parser')
    detail_table = tableSoup.find("table", class_="list")
    rows = detail_table.find_all("tr")[1:]

    
    for row in rows:
        cols = row.find_all("td")
          
        if cols[0].get_text(strip=True)=="小計":
            subTotal = cols[1].get_text(strip=True)
            continue
        if cols[0].get_text(strip=True)=="送料":
            deliveryFee = cols[1].get_text(strip=True)
            continue
        if cols[0].get_text(strip=True)=="手数料":
            transactionFee = cols[1].get_text(strip=True)
            continue
        if cols[0].get_text(strip=True)=="合計":
            totalFee = cols[1].get_text(strip=True)
            orderSummary = OrderSummary(subTotal, deliveryFee, transactionFee, totalFee)
            orderSummaryList.append(orderSummary)
            continue

    
    return orderSummaryList

def extract_OrderItem(rTxt):
    orderList = []
    
    orderID =""
    orderItem =""
    itemUnitPrice=""
    itemQuantity =""
    
    

    tableSoup = BeautifulSoup(rTxt,'html.parser')
    detail_table = tableSoup.find("table", class_="list")
    rows = detail_table.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
                  
        if cols[0].get_text(strip=True)=="小計" or cols[0].get_text(strip=True)=="送料" or cols[0].get_text(strip=True)=="手数料" or cols[0].get_text(strip=True)=="合計":
            
            continue
        

        orderID = cols[0].get_text(separator=" ", strip=True).split()[0]
        orderItem = cols[1].get_text(separator=" ", strip=True)
        itemUnitPrice = cols[2].get_text(strip=True)
        itemQuantity = cols[3].get_text(strip=True)

        orderitem = OrderItem(orderID,orderItem,itemUnitPrice,itemQuantity)
       
        orderList.append(orderitem)

    if len(orderList) < 15:
        numOfNullRows = 15-len(orderList)
        orderList.extend([None]*numOfNullRows)
        
    return orderList

# Initialize session_state values if not set
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "email" not in st.session_state:
    st.session_state.email = ""
if "password" not in st.session_state:
    st.session_state.password = ""

# --- Login form ---
if not st.session_state.logged_in:
    st.title("Login Page")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
       

    if submitted:
            if checkCredential(email, password):
                st.session_state.logged_in = True
                st.session_state.email = email
                st.session_state.password = password
                st.success("Login successful!")
                st.rerun()  # Force reload → but session_state keeps the values
            else:
                st.error("Invalid credentials")

# --- Main app (only after login) ---
else:
    st.title("Torahebi Statement of Delivery Generation Tools")
    
    # Date inputs
    start_date = st.date_input("Start Date", date.today())
    end_date = st.date_input("End Date", date.today())

    # File uploader for Word template
    uploaded_template = st.file_uploader("Upload Word Template (.docx)", type=["docx"])

    # Submit button
    if st.button("Generate Report"):
        if not uploaded_template:
            st.error("Please upload a Word template.")
        else:
            
            payload ={
                'mailaddress' : st.session_state.email,
                'password' : st.session_state.password
            }
            with requests.session() as session:
                generated_reports  = []
                s = session.post(LOGIN_URL, data=payload)
                m = session.get(searchResultURL_Preflex+str(start_date)+"&s_to="+str(end_date)+searchResultURL_Suflex)
                
                extract_OrderLink(m)
                
                #get how many page
                found_pages = getPages(m)
                for page in found_pages:

                    p = session.get(page)
                    extract_OrderLink(p)
                
                for found_link in found_links:
                    #get the html of the order page
                    r = session.get(found_link)
                    #append each html into list
                    
                    orderNumber, customeName = extract_CustomerName(r.text)
                    orderSummarys = extract_OrderSummary(r.text)
                    orderItems = extract_OrderItem(r.text)

                    for orderSummary in orderSummarys:

                        tax8Amount = round(int(orderSummary.subtotal.translate(translation_table)) - (int(orderSummary.subtotal.translate(translation_table)) / 1.08 ))

                        context = {

                            'customer_name' : customeName,
                            'subtotal' : orderSummary.subtotal,
                            'transaction_fee' : orderSummary.transFee,
                            'delivery_fee' : orderSummary.deliveryFee,
                            'tax_8' : f"{tax8Amount:,.0f}" + "円" ,
                            'total' : orderSummary.total,
                            'items': orderItems

                        }

                        doc = DocxTemplate(uploaded_template)
                        doc.render(context)

                        # save in memory
                        buffer = io.BytesIO()
                        doc.save(buffer)
                        buffer.seek(0)

                        # name the doc and add to list
                        fileName = orderNumber + "_納品書.docx"
                        generated_reports.append((fileName, buffer))
                
                # zip all doc
                
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    for fileName, fileBuffer in generated_reports:
                        zf.writestr(fileName, fileBuffer.getvalue())

                zip_buffer.seek(0)

                # let user download
                st.download_button(
                    label="Download all Statement of Delivery (ZIP)",
                    data=zip_buffer,
                    file_name="reports.zip",
                    mime="application/zip"
                )
            
                

            
            
           
            