import pandas as pd
import logging
from ingestion_db import ingest_db
from sqlalchemy import create_engine
import time

logging.basicConfig(
    filename='logs/get_vendor_summary.log',
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="a"
)

def create_vendor_summary(conn):
    vendor_sales_summary = pd.read_sql_query("""
    WITH FreightSummary AS (
        SELECT
            VendorNumber,
            SUM(Freight) AS FreightCost
        FROM vendor_invoice
        GROUP BY VendorNumber
    ),
    
    PurchaseSummary AS (
        SELECT
            p.VendorNumber,
            p.VendorName,
            p.Brand,
            p.Description,
            p.PurchasePrice,
            pp.Price AS ActualPrice,
            pp.Volume,
            SUM(p.Quantity) AS TotalPurchaseQuantity,
            SUM(p.Dollars) AS TotalPurchaseDollars
        FROM purchases p
        JOIN purchase_prices pp
            ON p.Brand = pp.Brand
        WHERE p.PurchasePrice > 0
        GROUP BY
            p.VendorNumber,
            p.VendorName,
            p.Brand,
            p.Description,
            p.PurchasePrice,
            pp.Price,
            pp.Volume
    ),
    
    SalesSummary AS (
        SELECT
            VendorNo,
            Brand,
            SUM(SalesQuantity) AS TotalSalesQuantity,
            SUM(SalesDollars) AS TotalSalesDollars,
            SUM(SalesPrice) AS TotalSalesPrice,
            SUM(ExciseTax) AS TotalExciseTax
        FROM sales
        GROUP BY VendorNo, Brand
    )
    
    SELECT
        ps.VendorNumber,
        ps.VendorName,
        ps.Brand,
        ps.Description,
        ps.PurchasePrice,
        ps.ActualPrice,
        ps.Volume,
        ps.TotalPurchaseQuantity,
        ps.TotalPurchaseDollars,
        ss.TotalSalesQuantity,
        ss.TotalSalesDollars,
        ss.TotalSalesPrice,
        ss.TotalExciseTax,
        fs.FreightCost
    FROM PurchaseSummary ps
    LEFT JOIN SalesSummary ss
        ON ps.VendorNumber = ss.VendorNo
       AND ps.Brand = ss.Brand
    LEFT JOIN FreightSummary fs
        ON ps.VendorNumber = fs.VendorNumber
    ORDER BY ps.TotalPurchaseDollars DESC
    """, engine)
    return vendor_sales_summary


def clean_data(vendor_sales_summary):
    
    #converting volume feature to Numeric
    vendor_sales_summary['Volume']=vendor_sales_summary['Volume'].astype('float')

    #removed leading and trailing spaces from VendorName col
    vendor_sales_summary['VendorName']=vendor_sales_summary['VendorName'].str.strip()
    #removed leading and trailing spaces from Description col
    vendor_sales_summary['Description']=vendor_sales_summary['Description'].str.strip()

    #filling missing data with 0's
    vendor_sales_summary.fillna(0,inplace=True)

    #feature engineering
    vendor_sales_summary['GrossProfit']=vendor_sales_summary['TotalSalesDollars']-vendor_sales_summary['TotalPurchaseDollars']
    vendor_sales_summary['ProfitMargin']=(vendor_sales_summary['GrossProfit']/vendor_sales_summary['TotalSalesDollars'])*100
    vendor_sales_summary['StockTurnover'] = vendor_sales_summary['TotalSalesQuantity']/vendor_sales_summary['TotalPurchaseQuantity']
    vendor_sales_summary['SalestoPurchaseRatio']=vendor_sales_summary['TotalSalesDollars']/vendor_sales_summary['TotalPurchaseDollars']

    return vendor_sales_summary


if __name__=='__main__':
    #creating database connection
    engine=create_engine(
    "mysql+pymysql://root:password@localhost:3306/vendor_data"
    )
    
    logging.info('Creating Vendor Summary Table....')
    start=time.time()
    summary_table=create_vendor_summary(engine)
    logging.info(f'Time taken {time.time()-start} minutes for Creating Vendor Summary Table.')
    
    logging.info('Cleaning data.....')
    start=time.time()
    clean_df=clean_data(summary_table)
    logging.info(f'Time taken {time.time()-start} minutes for cleaning data.')
    logging.info(clean_df.head())

    logging.info('Ingesting Data...')
    start=time.time()
    ingest_db(clean_df,name='vendor_sales_summary',engine)
    logging.info(f'Time taken {time.time()-start} minutes for Ingesting Data.')
    logging.info('Completed')
    
    