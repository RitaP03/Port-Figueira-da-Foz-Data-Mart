# Port of Figueira da Foz: Data Mart and Decision Support Dashboard
 
Academic project developed for the **Information Systems II** course at the **Polytechnic Institute of Coimbra (ISEC)**, in a team of two (Ana Rita Pessoa and David Matos).
 
The project builds a **Data Mart** for the analysis of vessel trips arriving at the Port of Figueira da Foz. Data from an operational **MySQL** database and a **CSV** file is integrated into a **SQL Server** star schema using **Python** ETL scripts, and explored in a **Power BI** dashboard.
 
## Tech stack
 
Python (`pyodbc`, `mysql-connector`, `csv`) · MySQL · SQL Server · Power BI (DAX)
 
## Data model
 
Star schema at **trip level** (one row per trip in the fact table):
 
| Table | Description |
|---|---|
| `fact_viagem` | Trips, with revenue from fees (EUR) and TEU/weight/containers measures |
| `dim_barco` | Vessel, type, size, registration country and operating company |
| `dim_condutor` | Captain, certification, age |
| `dim_localizacao` | Ports; used as both **origin** and **destination** (role-playing dimension) |
| `dim_tempo` | Date dimension generated from the arrival date |
| `dim_detalhes` | Trip type and status |
 
## ETL
 
| Script | What it does |
|---|---|
| `ETL_MySQL_para_DW_Portuario.py` | Loads `dim_barco`, `dim_localizacao`, `dim_condutor` and the completed trips from MySQL into SQL Server |
| `ETL_CSV_para_DW_Portuario.py` | Loads trips with Figueira da Foz as destination from `dados.csv`, creating missing dimension members on demand, generating `dim_tempo`, parsing dates and decimal commas, and converting fees from USD to EUR (fixed rate of 0.87) |
 
**Run order:** MySQL script first (it clears and reloads the dimensions and the fact table), then the CSV script.
 
**Configuration:** connection settings are read from environment variables (`MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PWD`, `MYSQL_DB`, `MSSQL_HOST`, `MSSQL_USER`, `MSSQL_PWD`, `MSSQL_DB`, `CSV_DADOS_PORTO`). Set them before running.
 
## Dashboard
 
`KPI.pbix` contains 7 KPIs and a final dashboard with filters by country, year, vessel type and captain certification:
 
1. Trip volume by origin country
2. Total fee revenue by origin country (with map)
3. Trips by captain certification
4. Trips by vessel type
5. Trips per month
6. Average fee revenue per trip by vessel type
7. Share of trips by weekday
## Repository contents
 
| File | Content |
|---|---|
| `si2_2526_tp_*.pdf` | Project report |
| `ETL_MySQL_para_DW_Portuario.py`, `ETL_CSV_para_DW_Portuario.py` | ETL scripts |
| `KPI.pbix` | Power BI report |
| `dados.csv` | Trip data used by the CSV ETL |
| `mysql_dataset_portuario_full.sql` | Operational MySQL dataset |
 
## Known limitations
 
This is a course project, and some limitations are worth knowing:
 
- **Revenue is only available for part of the data.** Trips loaded from MySQL (11,956 of 13,956 in the final model) have revenue set to 0, because the operational database holds no fee data. Revenue KPIs, and in particular the *average revenue per trip*, are therefore diluted by these rows. Treating missing revenue as `NULL` would be more accurate.
- **Part of the CSV is synthetic.** The CSV combines the data provided in the assignment with additional rows generated with Mockaroo, so the patterns in the dashboard (for example, the weight of Portugal as origin country) reflect the generated data and not real port activity.
- **TEU, weight and number of containers are 0**, because the source data does not include them.
- **Captains are identified by name** in the CSV ETL, so different people with the same name are merged into one.
- **The CSV ETL is not idempotent**: running it twice inserts the trips twice.
- **The report's dashboard capture (Fig. 12) and the sizing estimate (Section 10) were made with an earlier load of 1,000 trips.** The final model in `KPI.pbix` has 13,956 trips.
