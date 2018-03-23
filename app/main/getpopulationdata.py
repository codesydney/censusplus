from .dbconnection import get_db_connection, get_db_cursor
from psycopg2.extensions import AsIs
import operator

#matplotlib
import numpy
import matplotlib
matplotlib.use('agg')
import matplotlib.pyplot as plt
from io import BytesIO
#import base64

def get_population_data(InputSSC, InputSuburb):
    """get census data about population 
    from census_2016_data.ssc_g01.
    """
    result_data = [];

    # get column's description from census_2016_data.metadata_stats
    with get_db_cursor() as pg_cur:

        search_stats_tuple = tuple(["G"+str(no) for no in range(1,4)]) 
        #hardcode: 4
        #I only need G1 (total males), G2 (total females) and G3 (total persons) 
        #They are all in table: census_2016_data.ccs_g1
        # print ("getpopulationdata.py::get_population_data: search_stats_tuple = ",search_stats_tuple);

        sql_template = "SELECT sequential_id AS id, " \
              "lower(table_number) AS \"table\", " \
              "replace(long_id, '_', ' ') AS description, " \
              "column_heading_description AS type, " \
              "'values' as maptype " \
              "FROM {0}.metadata_stats " \
              "WHERE sequential_id IN %s " \
              "ORDER BY sequential_id".format('census_2016_data')

        sql = pg_cur.mogrify(sql_template, (AsIs(search_stats_tuple),)) 

        print("===>getpopulationdata.py::get_population_data: sql:", sql)
    
        try:
            #pg_cur.execute(sql, (search_stats_tuple,))
            pg_cur.execute(sql)
        except psycopg2.Error:
            return "I can't SELECT:<br/><br/>" + sql

        # Retrieve the results of the query
        rows = pg_cur.fetchall()
    

    #rows = db.engine.execute(sql)    

    # output is the main content, row_output is the content from each record returned
    response_dict = []

    # For each row returned assemble a dictionary
    #no = 1;
    for row in rows:
        feature_dict = dict(row)
        #no determine the order in result page.
        #feature_dict["no"] = int(re.sub("[A-Za-z]","",feature_dict["id"]))
        feature_dict["no"] = 1;
        if feature_dict["id"] == 'G1':
            feature_dict["no"] = 2;
        elif feature_dict["id"] == 'G2':
            feature_dict["no"] = 3;
        elif feature_dict["id"] == 'G3':
            feature_dict["no"] = 1;            
        feature_dict["id"] = feature_dict["id"].lower()
        feature_dict["table"] = feature_dict["table"].lower()
        #print(feature_dict)
        # add dict to output array of metadata
        response_dict.append(feature_dict)
        #no += 1

    # output_array.append(output_dict)

    # print("Got metadata for {0} in {1}".format(boundary_name, datetime.now() - start_time))

    # # Assemble the JSON
    # response_dict["boundaries"] = output_array

    #sort response_dict by id: g1~g108
    response_dict.sort(key=operator.itemgetter('no'))
    #print("views:py::get_population_data: response_dict = ",response_dict)


    #get values of census item from g1 to g108
    with get_db_cursor() as pg_cur:

        search_stats_tuple = tuple(["G"+str(no) for no in range(1,10)]) 
        # hardcode: 10
        # the max value can be set up to 109. They are all in table: census_2016_data.ccs_g1
        # print ("getpopulationdata.py::get_population_data: search_stats_tuple = ",search_stats_tuple);

        #hardcode
        sql_template2 = "SELECT tab.g1, tab.g2, tab.g3, tab.g4, tab.g5, tab.g6, tab.g7, tab.g8, tab.g9, " \
            "tab.g10, tab.g11, tab.g12, tab.g13, tab.g14, tab.g15, tab.g16, tab.g17, tab.g18, tab.g19, " \
            "tab.g20, tab.g21, tab.g22, tab.g23, tab.g24, tab.g25, tab.g26, tab.g27, tab.g28, tab.g29, " \
            "tab.g30, tab.g31, tab.g32, tab.g33, tab.g34, tab.g35, tab.g36 " \
              "FROM {0}.%s_%s AS tab " \
              "WHERE tab.region_id = '%s'" \
              .format('census_2016_data')
        #print("==>main/getpopulationdata.py::get_data: enter line 389")

        sql2 = pg_cur.mogrify(sql_template2, (AsIs("ssc"), AsIs("g01"), AsIs(InputSSC)))
        #hardcode
        

        # print("===>getpopulationdata.py::get_result_metadata: sql2:", sql2)
    
        try:
            pg_cur.execute(sql2)
        except psycopg2.Error:
            return "I can't SELECT:<br/><br/>" + sql2

        # Retrieve the results of the query
        value_row = pg_cur.fetchone()
    
        value_dict = dict(value_row);
        #print("getpopulationdata.py::get_result_metadata the result of sql2:",value_dict)

        response2_list = []
        for response_item in response_dict:
        # add more data to response_item 1:
            response2_item = {}
            response2_item["no"] = response_item["no"]
            response2_item["id"] = response_item["id"]
            response2_item["description"] = response_item["description"]
            print(response_item["id"].lower());
            # for total persons
            if response_item["id"].lower() == "g3": 
                table1 = []
                table1.append(["suburb","year","value"])
                table1.append([InputSuburb,"2016",int(value_dict["g3"])])
                # print("enter",table1);
                response2_item['numoftable'] = 1
                response2_item['table'] = [table1]
                response2_item['numofchart'] = 1
                #make chart
                x_values = [1,2,3,4,5,6,7,8,9,10,11]
                x_labels = ["0-4","5-14","15-19","20-24","25-34","35-44","45-54","55-64","65-74","75-84",">85"]
                y_values = [int(value_dict["g6"]),int(value_dict["g9"]),int(value_dict["g12"]),int(value_dict["g15"]), 
                            int(value_dict["g18"]),int(value_dict["g21"]),int(value_dict["g24"]),int(value_dict["g27"]), \
                            int(value_dict["g30"]),int(value_dict["g33"]),int(value_dict["g36"])]
                filepath = 'app/main/static'
                filename = 'chart_g3_01.png'
                chart1 = create_population_chart_g3(x_values,x_labels,y_values,filepath,filename)
                response2_item['chart'] = [filename]
                
            # for total males    
            elif response_item["id"].lower() == "g2": 
                table1 = []
                table1.append(["suburb","year","value"])
                table1.append([InputSuburb,"2016",int(value_dict["g2"])])
                # print("enter",table1);
                response2_item['numoftable'] = 1
                response2_item['table'] = [table1]
                response2_item['numofchart'] = 1
                # make chart
                x_values = [1,2,3,4,5,6,7,8,9,10,11]
                x_labels = ["0-4","5-14","15-19","20-24","25-34","35-44","45-54","55-64","65-74","75-84",">85"]
                y_values = [int(value_dict["g5"]),int(value_dict["g8"]),int(value_dict["g11"]),int(value_dict["g14"]), 
                            int(value_dict["g17"]),int(value_dict["g20"]),int(value_dict["g23"]),int(value_dict["g26"]), \
                            int(value_dict["g29"]),int(value_dict["g32"]),int(value_dict["g35"])]
                filepath = 'app/main/static'
                filename = 'chart_g3_02.png'
                chart1 = create_population_chart_g3(x_values,x_labels,y_values,filepath,filename)
                response2_item['chart'] = [filename]

            # for total females    
            elif response_item["id"].lower() == "g1": 
                table1 = []
                table1.append(["suburb","year","value"])
                table1.append([InputSuburb,"2016",int(value_dict["g1"])])
                # print("enter",table1);
                response2_item['numoftable'] = 1
                response2_item['table'] = [table1]
                response2_item['numofchart'] = 1
                # make chart
                x_values = [1,2,3,4,5,6,7,8,9,10,11]
                x_labels = ["0-4","5-14","15-19","20-24","25-34","35-44","45-54","55-64","65-74","75-84",">85"]
                y_values = [int(value_dict["g4"]),int(value_dict["g7"]),int(value_dict["g10"]),int(value_dict["g13"]), 
                            int(value_dict["g16"]),int(value_dict["g19"]),int(value_dict["g22"]),int(value_dict["g25"]), \
                            int(value_dict["g28"]),int(value_dict["g31"]),int(value_dict["g34"])]
                filepath = 'app/main/static'
                filename = 'chart_g3_03.png'
                chart1 = create_population_chart_g3(x_values,x_labels,y_values,filepath,filename)
                response2_item['chart'] = [filename]

            response2_list.append(response2_item)

    #print(response2_list);    
    return response2_list;

def create_population_chart_g3(x_values,x_labels,y_values,filepath,filename):
    ### Generating X,Y coordinaltes to be used in plot
    ### Generating The Plot
    plt.bar(x_values,y_values)
    plt.xticks(x_values, x_labels)
    ### Saving plot to disk in png format
    filepathname = filepath+'/'+filename
    plt.savefig(filepathname)

    ### Rendering Plot in Html
    figfile = BytesIO()
    plt.savefig(figfile, format='png')
    # to clear old data
    plt.clf()
    plt.cla()
    plt.close()
    
    # figfile.seek(0)
    # figdata_png = base64.b64encode(figfile.getvalue())
    # result = figdata_png
    # return result