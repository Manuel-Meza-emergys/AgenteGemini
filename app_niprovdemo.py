import os
import vertexai
from vertexai.language_models import ChatModel, InputOutputTextPair, ChatMessage
import streamlit as st

os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_KEY"]["key"]

#os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = path
#os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\AI\Google\agentdata\emergys-genai2.json'
#os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(st.secrets["GOOGLE_CREDENTIALS"])
#os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = st.secrets["GOOGLE_CREDENTIALS"]["credentials"]
#os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = emergys_genai
import vertexai
vertexai.init(project="emergys-genai", location="us-central1")

import time

from google.cloud import bigquery
import streamlit as st
from vertexai.generative_models import (
    FunctionDeclaration,
    Tool,
    GenerationConfig,
    GenerativeModel,
    HarmBlockThreshold,
    HarmCategory,
    Part,
)
client = bigquery.Client()
#db_id = 'emergys-genai.BasesParaAgentes'
#db_id_ = 'emergys-genai.BasesParaAgentes.RegistrosRPA_Nipro'
#fecha_inicial = '2024-05-15 13:52:00 UTC'
#fecha_final = '2024-05-22 15:28:00 UTC'

def get_schema_table(database_id_table):
    client = bigquery.Client()
    get_columns = client.get_table(database_id_table)
    get_columns = get_columns.to_api_repr()
    schem = str([element['name'] for element in get_columns["schema"]["fields"]]).replace('[','').replace(']','')
    return database_id_table, schem

def data_agent(pregunta):
    #Esquema
    #db_id_ = 'emergys-genai.BasesParaAgentes.RegistrosRPA_Nipro'
    #db_id_ = 'emergys-genai.BasesParaAgentes.NiproOrderEntry'
    #db_id_ = 'emergys-genai.BasesParaAgentes.NiproOrderMay'
    db_id_ = 'emergys-genai.BasesParaAgentes.NiproOrderAug'
    base, schema = get_schema_table(db_id_)
    #LLamada de Función
    sql_query_func = FunctionDeclaration(
    name = "consulta_sql",
    description="Only to obtain information from Bigquery data using SQL queries, do not use this function if it is not for a query",
    parameters={
        "type":"object",
        "properties":{
            "consulta":{
                "type":"string",
                "description":"Single-line SQL query that will help provide quantitative answers to the user's question when run on a BigQuery data set and table. In the SQL query, always use the entire data set and table names."
            }
        },
        "required":[
          "consulta",  
        ],
    },
    )

    tools = Tool(
        function_declarations=[
            sql_query_func,
        ],
    )
    #Prompt Principal
    prompt = f"""
    You are a specialist SQL programmer agent. Your goal is to create SQL queries for BigQuery, according to the instructions given by the user.
    You will also be able to answer simple questions related to the database to use.


    The database schema has the table {base} with its respective columns {schema}. As a SQL programmer you must follow the following
    design tips:

    1. Simple Queries:
        - Extract data from a specific table.
        - Filter records according to certain criteria.
        - Sort results by one or more columns.
    
    2. Advanced Queries:
        - Perform unions (JOIN) between multiple tables.
        - Group data and calculate aggregates (SUM, AVG, COUNT, TIMESTAMP_DIFF, CURRENT_TIMESTAM, etc.).
        - Subqueries and nested queries.
        - Queries based on tables.
    


    CREATE TABLE STRUCTURES TO DO COMPLEX SEARCHES, AS SHOWN BELOW:

    - Natural Language: given the table `{db_id_}` extract the highest value of 'Unit Price' when 'SoldToName' = 'DaVita' and save it in table1. From table1 give me the columns 'Download Datetime', 'Sender' and 'Unit Price'
    - Reasoning: Analyze the question step by step to choose this example, HERE THEY ASK YOU FOR A HIGHEST VALUE.
    - SQL Translation: WITH tabla1 AS (SELECT `Download Datetime`,`Sender`,`Unit Price` FROM  `{db_id_}` WHERE `SoldToName` = 'DaVita' ORDER BY  `Unit Price` DESC LIMIT 1) SELECT  `Download Datetime`, `Sender`, `Unit Price` FROM  tabla1;
    - Answer: You will indicate the result with a brief explanation of the results obtained

    - Natural Language: given the table `{db_id_}`, extract the lowest value of 'Unit Price' when 'SoldToName' = 'DaVita' and save it in table1. From table1 give me the columns 'Download Datetime', 'Sender' and 'Unit Price'
    - Reasoning: Analyze the question step by step to choose this example, HERE THEY ASK YOU FOR A LOWER VALUE.
    - SQL Translation: WITH tabla1 AS (SELECT `Download Datetime`, `Sender`, `Unit Price` FROM `{db_id_}` WHERE  `SoldToName` = 'DaVita' ORDER BY `Unit Price` ASC LIMIT 1) SELECT `Download Datetime`, `Sender`, `Unit Price` FROM tabla1;
    - Answer: You will indicate the result with a brief explanation of the results obtained

    Examples of Business questions:

    - Natural Language: Can you give me the total purchase for the DaVita customer for the last 30 days?
    - Reasoning: Analyze the question step by step to choose this example, they ask you for the purchase total (it means the total of the 'Ext Price' column) they also give you the customer (from the 'Sender' column) and the date of to today to 30 days ago.
                    use the following steps: given the table `{db_id_}` add the value of 'Ext Price' when 'Sender' = 'DaVita' of the last 30 days, to calculate the dates obtain the data from the column ' Datetime Of Receipt' and save it in PriceMonth.
    - SQL Translation: WITH tabla1 AS (SELECT SUM(`Ext Price`) AS TotalPrice FROM 
                            `{db_id_}` WHERE `Sender` = 'DaVita' AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), `Datetime Of Receipt`, DAY) <= 90) SELECT TotalPrice FROM tabla1;
    - Answer: Mention indicating that it is the purchase total of the 'Sender' customer with $ and two significant figures after the decimal point. 
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural language: Give me a purchase comparison for DaVita and ROPER ST. FRANCIS HEALTHCARE of the last month.
    - Reasoning: Analyze the clients provided by the user to be able to build the query, if it is the last month, consider 30 days.
    - SQL Translation:WITH tabla1 AS (SELECT Sender, SUM(`Ext Price`) AS TotalExtPrice FROM `{db_id_}`
                        WHERE `Sender` IN ('ROPER ST. FRANCIS HEALTHCARE', 'DaVita') AND TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), `Datetime Of Receipt`, DAY) <= 30
                            GROUP BY Sender) SELECT * FROM tabla1;
    - Answer: Give a bullet list of each 'Sender' the total amount of the 'Sender' client with $ and two significant figures after the decimal point.
                for example:
                The total purchase in the last 30 days:
                * Davita: $ 102,738.60
                * FRANCIS HEALTHCARE: $ 720.00

                Replace the 'Sender' with the following rule:
                if Davita, replace with Kansas Medical Sup
                if Medline Industries LP, replace with California Medical Services

                If there is no response from the database you can respond "The data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: I am interested in having a comparison of purchases of DaVita, Atrium Health and AOSS Medical Supply LLC clients including the minimum and maximum purchase amount of each one
    - Reasoning: You are asked that given the table `{db_id_}` extract when the column 'Sender' = 'DaVita' and 'Sender' = 'Atrium Health' and 'Sender' = 'AOSS Medical Supply LLC' and save them in table 1 and extract the Maximum and Minimum number of 'Ext Price' for each 'Sender' mentioned
    - SQL Translation: WITH tabla1 AS (SELECT * FROM `{db_id_}`
                        WHERE `Sender` IN ('DaVita', 'Atrium Health', 'AOSS Medical Supply LLC'))
                        SELECT `Sender`,
                            MAX(`Ext Price`) AS MaxExtPrice,
                            MIN(`Ext Price`) AS MinExtPrice
                        FROM tabla1 GROUP BY `Sender`;
    - Answer: Shows the data ordered as follows: For example:
                                    * DaVita: Max: $ 12,000.00, Min: $ 10,000.00
                                    * Atrium Health: Max: $ 12,000.00, Min: $ 10,000.00
                                    * AOSS Medical Supply LLC: Max: $ 12,000.00, Min: $ 10,000.00
    - Response if you did not receive a result of the query or it was wrong: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: I am interested in having a comparison of purchases from DaVita, Atrium Health and AOSS Medical Supply LLC clients in the last 5 days including the minimum and maximum purchase amount of each one, or,
                        Create a table to compare purchases of DaVita, Atrium Health and AOSS Medical Supply LLC customers in the last 5 days. Include the minimum and maximum purchase amount of each on
    - Reasoning: You are asked that given table `{db_id_}` extract when column 'Sender' = 'DaVita' and 'Sender' = 'Atrium Health' and 'Sender' = 'AOSS Medical Supply LLC' and save them in table1 and extract the Maximum and Minimum number of 'Ext Price' for each 'Sender' mentioned and save it in table2. From table 2, give me the maximum and minimum amounts of each 'Sender' only from the last 5 days to the current date, you must subtract 5 days from this date, FOR THIS EXAMPLE TAKE INTO ACCOUNT THE FINAL DATE AS 2024-05-22
    - SQL Translation: WITH tabla1 AS (SELECT * FROM `{db_id_}` WHERE `Sender` IN ('DaVita', 'Atrium Health', 'AOSS Medical Supply LLC')), tabla2 AS (SELECT  `Sender`, MAX(`Ext Price`) AS MaxExtPrice, MIN(`Ext Price`) AS MinExtPrice FROM tabla1 WHERE DATE(`Datetime Of Receipt`) >= DATE_SUB('2024-05-22', INTERVAL 5 DAY) GROUP BY `Sender`) SELECT `Sender`, MaxExtPrice, MinExtPrice FROM tabla2;
    - Answer: Shows the data ordered as follows: 
                                    For example:
                                    * DaVita: Max: $ 12,000.00, Min: $ 10,000.00
                                    * Atrium Health: Max: $ 12,000.00, Min: $ 10,000.00
                                    * AOSS Medical Supply LLC: Max: $ 12,000.00, Min: $ 10,000.00
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: Give me a comparison of purchases of DaVita, Atrium Health and AOSS Medical Supply LLC customers including the minimum and maximum purchase amount of each from 2024-05-15 to 2024-05-19
    - Reasoning: you are asked to extract given table `medications` when column 'Sender' = 'DaVita' and 'Sender' = 'Atrium Health' and 'Sender' = 'AOSS Medical Supply LLC' and save them in table1 and extract the Maximum and Minimum number of 'Ext Price' for each 'Sender' mentioned and save it in table2. From table 2, give me the maximum and minimum amounts of each 'Sender' from 2024-05-15 to 2024-05-19, THE USER CAN GIVE OTHER INTERVAL DATES
    - SQL Translation: WITH tabla1 AS (SELECT * FROM `{db_id_}` WHERE `Sender` IN ('DaVita', 'Atrium Health', 'AOSS Medical Supply LLC')),
                        tabla2 AS (SELECT  `Sender`, MAX(`Ext Price`) AS MaxExtPrice, MIN(`Ext Price`) AS MinExtPrice FROM tabla1 WHERE DATE(`Datetime Of Receipt`) BETWEEN '2024-05-15' AND '2024-05-19' GROUP BY `Sender`)
                            SELECT `Sender`, MaxExtPrice, MinExtPrice FROM tabla2;
    - Answer: Shows the data ordered as follows: 'Sender', MonMax: $MaxExtPrice, MontMin: MinExtPrice. 
                                    For example:
                                    * DaVita: Max: $ 12,000.00, Min: $ 10,000.00
                                    * Atrium Health: Max: $ 12,000.00, Min: $ 10,000.00
                                    * AOSS Medical Supply LLC: Max: $ 12,000.00, Min: $ 10,000.00
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: Give me the products that DaVita consumes
    - SQL Translation: WITH tabla1 AS (SELECT DISTINCT `Item` FROM `{db_id_}` WHERE `Sender` = 'DaVita') SELECT * FROM tabla1;
    - Response: shows a list with the results. 
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"


    - Natural Language: what is the top 5 customers who have purchased the most?
    - SQL Translation: WITH tabla1 AS (SELECT `Sender`, SUM(`Ext Price`) AS `MontoTotal` FROM `{db_id_}` GROUP BY `Sender`) SELECT `Sender`, `MontoTotal` FROM tabla1 ORDER BY `MontoTotal` DESC LIMIT 5;
    - Answer: Mention the total amount of the 'Sender' client with $ and two significant figures after the decimal point. Replace the 'Sender' result with the following rule:
                if  Medline Industries LP, replace with California Medical Services
                if  3J Medical Supplies Inc, replace with Medical Supplies Inc
                if  vantive us healthcare llc, replace with North Medical Sup
                if  VANTIVE US HEALTHCARE LLC, replace with US HEALTHCARE LLC
                if  DaVita, replace with Kansas Medical Sup
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: what is the top 5 customers who have bought the most this week?
    - SQL Translation: WITH tabla1 AS (SELECT `Sender`, SUM(`Ext Price`) AS `MontoTotal` FROM `{db_id_}` WHERE DATE(`Datetime Of Receipt`) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY) GROUP BY `Sender`) SELECT `Sender`, `MontoTotal` FROM tabla1 ORDER BY `MontoTotal` DESC LIMIT 10;
    - Answer: Mention the total amount of the 'Sender' client with $ and two significant figures after the decimal point. 
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: Give me the total sales for this week
    - SQL Translation: SELECT SUM(`Ext Price`) AS `TotalExtPrice` FROM `{db_id_}` WHERE DATE(`Datetime Of Receipt`) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
    - Answer: Mention the total amount in the format $(total amount with two figures after the period). 
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: Give me the lowest order amount and its customer
    - SQL Translation: WITH tabla1 AS (SELECT `Sender`, `Ext Price` FROM `{db_id_}` ORDER BY `Ext Price` ASC LIMIT 1) SELECT `Sender`, `Ext Price` FROM tabla1;
    - Answer: Mention the client: and the total amount with the format $ (total amount with two figures after the period). 
    - - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: What is the top 5 products that have been purchased the most?
    - SQL Translation: WITH tabla1 AS (SELECT `Item`, SUM(`Ext Price`) AS `MontoTotal` FROM `{db_id_}` GROUP BY `Item`) SELECT `Item`, `MontoTotal` FROM tabla1 ORDER BY `MontoTotal` DESC LIMIT 5;
    - Answer: Mention the total amount of the product 'Item' with $ and two significant figures after the decimal point. 
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: Give me that same top 5 products including the maximum and minimum price of each one
    - SQL Translation: WITH tabla1 AS (SELECT `Item`, SUM(`Ext Price`) AS `MontoTotal` FROM `{db_id_}` GROUP BY `Item`), tabla2 AS (SELECT `Item`, `MontoTotal` FROM tabla1 ORDER BY `MontoTotal` DESC LIMIT 5) SELECT t2.`Item`, MAX(m.`Ext Price`) AS `Max`, MIN(m.`Ext Price`) AS `Min` FROM tabla2 t2 JOIN `{db_id_}` m ON t2.`Item` = m.`Item` GROUP BY t2.`Item`;
    - Answer: Shows the data ordered as follows: Product[Name], MonMax[Maximum Amount], MontMin[Minimum Amount]. 
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: Which customers have purchased BL+A430/V912
    - SQL Translation: WITH tabla1 AS (SELECT DISTINCT `Sender`, `Item` FROM `{db_id_}` WHERE `Item` = 'BL+A430/V912') SELECT `Sender`, `Item` FROM tabla1;
    - Answer: Give a bullet list of each 'Sender'. 
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"


    - Natural Language: Generate a sales summary for the last 7 days that includes the total sales and the 3 customers with the highest purchase amount.
    - SQL Translation: WITH TotalSales AS (
                SELECT 
            SUM(`Ext Price`) AS `TotalExtPrice`
                FROM `{db_id_}`
                WHERE DATE(`Datetime Of Receipt`) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
            ),
            UniqueSenders AS (
                SELECT 
                    `Sender`,
                    SUM(`Ext Price`) AS `SenderTotalExtPrice`
                FROM `{db_id_}`
                WHERE DATE(`Datetime Of Receipt`) >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
                GROUP BY `Sender`
                ORDER BY `SenderTotalExtPrice` DESC
                LIMIT 3
            )
            SELECT 
                (SELECT `TotalExtPrice` FROM TotalSales) AS `TotalSalesLast7Days`,
                `Sender`,
                `SenderTotalExtPrice`
            FROM UniqueSenders;
    - Answer: Shows all items as a list and replace the names of `Sender` as following:
                if Medline Industries LP, replace with California Medical Services
                if 3J Medical Supplies Inc, replace with Medical Supplies Inc
                if DVMed supply, replace with Medin supply
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: Present me a list of the products with a price greater than 1100 usd and the total sales of those products in the last 10 days
    - SQL Translation: WITH tabla1 AS (
                    SELECT *
                    FROM `{db_id_}`
                    WHERE DATE(`Datetime Of Receipt`) >= DATE_SUB(CURRENT_DATE(), INTERVAL 10 DAY) AND `Ext Price` > 1100
                    )
                    Select DISTINCT `Item`, `Ext Price` FROM tabla1 limit 5
    - Answer: Shows all items as a list and you should replace the names on the list with the following 3 new names:
                      
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"


    - Natural Language: When was the last purchase order received for CF+609N product?
    - SQL Translation: SELECT `Datetime Of Receipt`, `Sender`, `Ext Price`
                        FROM `{db_id_}`
                        WHERE `Item` = 'CF+609N'
                          AND `Datetime Of Receipt` = (
                            SELECT MAX(`Datetime Of Receipt`)
                            FROM `{db_id_}`
                            WHERE `Item` = 'CF+609N'
                          ) LIMIT 1;
    - Answer: Shows all items as a list. If there is no response from the database you can respond "The data is not enough or incorrect to make a estimation, could you please rephrase your question?"

    - Natural Language: When was the last purchase order received for DaVita customer and what products were purchased, how much was the total amount?
    - SQL Translation: WITH UltimaFecha AS (
                        SELECT MAX(DATE(`Datetime Of Receipt`)) AS UltimaFecha
                        FROM `{db_id_}`
                    )
                    SELECT DISTINCT Item, `Ext Price`, `PO Number`
                    FROM `{db_id_}`
                    CROSS JOIN UltimaFecha
                    WHERE DATE(`Datetime Of Receipt`) = UltimaFecha.UltimaFecha
                        AND Sender = 'DaVita' LIMIT 5;
    - Answer: Shows all items as a list. 
    - Response if you did not receive a result of the query: "Sorry, the data is not enough or incorrect to make a estimation, could you please rephrase your question?"
    
    - Natural Language: What dog products sold the best?
    - SQL Translation: WITH tabla1 AS (SELECT Item, SUM(`Ext Price`) AS MontoTotal FROM 
                    `emergys-genai.BasesParaAgentes.NiproOrderMay` 
                    WHERE Item LIKE '%DOG%' GROUP BY Item) SELECT Item, 
                    MontoTotal FROM tabla1 ORDER BY MontoTotal DESC LIMIT 5;
    - Answer: If there is no response from the database you can respond: "Your question cannot be answered in relation to the present database, please, can you ask another question?"

    - Natural Language: what is the weather in SF
    - SQL Translation: WITH tabla1 AS (SELECT Item, SUM(`Ext Price`) AS MontoTotal FROM 
                    `emergys-genai.BasesParaAgentes.NiproOrderMay` 
                    WHERE Item LIKE '%weather%' GROUP BY Item) SELECT Item, 
                    MontoTotal FROM tabla1 ORDER BY MontoTotal DESC LIMIT 5;
    - Answer: If there is no response from the database you can respond: "Your question cannot be answered in relation to the present database, please, can you ask another question?"
    
    You must follow the precise instructions to assemble and create the query, you will be given a guide to create the SQL query.

    Important, if the user asks a question different from those presented above, please answer: Your question cannot be answered in relation to the present database, please, can you ask another question?

    Think step by step before generating your answer


    Question:
    """
    #Proceso Generativo
    prompt += pregunta
    agent = GenerativeModel(
        #"gemini-1.5-pro-preview-0514",
        "gemini-1.0-pro-001",
        generation_config = GenerationConfig(temperature=0),
        tools=[tools],
    )

    chat = agent.start_chat()
    response = chat.send_message(prompt)
    params = {}
    for key, value in response.candidates[0].content.parts[0].function_call.args.items():
        params[key] = value
    #print("Llamada de Función:\n")
    #print(response.candidates[0].content.parts[0].function_call.name)
    consulta_limpia = (params['consulta'].replace("\\n", " ").replace("\n", " ").replace("\\", ""))
    #print("\n\n")
    #print("Consulta Generada:\n")
    #print(consulta_limpia)
    if response.candidates[0].content.parts[0].function_call.name == "consulta_sql":
        query_job = client.query(query=consulta_limpia)
        api_response = query_job.result()
        api_response = str([dict(row) for row in api_response])
        api_response = api_response.replace("\\", "").replace("\n", "")
        #print("\n\n")
        #print("Respuesta de BigQuery:\n")
        #print(api_response)

        #print("Respuesta del Modelo al usuario:\n")
        response1 = chat.send_message(
            Part.from_function_response(
                name = response.candidates[0].content.parts[0].function_call.name,
                response={
                    "content":api_response
                },
            ),
        )
        respuesta = response1.candidates[0].content.parts[0].text
        completa = f"Consulta: {consulta_limpia} \n Respuesta de BD: {api_response} \n Respuesta del modelo: {respuesta}"
        consulta_res = f"Consulta: `{consulta_limpia}` \n Respuesta del modelo: {respuesta}"
    return respuesta






#st.image("Google_PaLM_Logo.svg.png", use_column_width=False, width=50)





def main():
    #st.set_page_config(page_title="Emergys Mexico")
    #st.header("Asistente Inteligente de Emergys México")

    #st.image("emergys1.png", use_column_width=False, width=400)
    #st.title("🌴 Google PALM chat-bison 💬")

    #st.title("Chat Básico")
    user_avatar = "🧔‍♂️"
    assitant_avatar = "🤖"
    
    # Entiendo que por cada sesión que se haga, se deben guardar variables en

    st.sidebar.title('AI Data Agent - NIPRO')
    st.sidebar.image("nipro1.png")

    
    
    #st.sidebar.title('Resumen de Reuniones')
    #uploaded_file = st.sidebar.file_uploader("Suba su archivo aquí")
    #st.sidebar.image("emergys1.png")
    
    # Se inicializa el historico del chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Muestra el chat de mensajes desde el historico cuando reinicias la app
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=user_avatar  if message["role"] == "user" else assitant_avatar):
            st.markdown(message["content"])

    #----------------------------Conversation with the LLM-------------------------------------
    # Accept user input
    if prompt := st.chat_input(f"Ask Gemini about your data..."):
        
        #mensajes = [ChatMessage(author = m["role"], content = m["content"]) for m in st.session_state.messages]
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Display user message in chat message container
        #-------------------------Human section-----------------------------------------
        with st.chat_message(name="user", avatar=user_avatar ):
            st.markdown(prompt)
        # Display assistant response in chat message container
        #-------------------------LLM section------------------------------------------
        with st.chat_message(name="assistant", avatar=assitant_avatar):
            with st.spinner("Thinking..."):
                message_placeholder = st.empty()
                full_response = ""
                #---------------------Estructura del llamado del modelo---------------
                # Not Stream
                full_response = data_agent(prompt)
                message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})



if __name__ == "__main__":
    main()