#########################################################################################################
#   Program Name : NSWEmploymentRateDatabasePrep.py                                                          #
#   Program Description:                                                                                #
#   This program prepares a SQLite table containing data about Employment status in NSW.                      #
#                                                                                                       #
#   Comment                                         Date                  Author                        #
#   ================================                ==========            ================              #
#   Initial Version                                 25/10/2017            Engramar Bollas               #
#   Prepared a blog                                 28/10/2017            Engramar Bollas        		#
#   testing new branch commit 			            30/10/2017	          Gerald Mills  	            #
#   testing new branch commit                       09/11/2017            about.me/kashif.islam         #
#   Updated for Employment Rate 					12/03/2018			  Albert Molina	                #
#########################################################################################################
import sqlite3
import sys

#######################################################################
### Create NSW_EMPLOYMENT_RATE Table                                     ### 
#######################################################################

conn = sqlite3.connect('NSW_EMPLOYMENT_RATE.sqlite')
cur = conn.cursor()

cur.executescript('''	
DROP TABLE IF EXISTS NSW_EMPLOYMENT_RATE;
 
CREATE TABLE NSW_EMPLOYMENT_RATE (
	YEAR              number(4),            
	LOCALITY          varchar(100),
	SUBURB            varchar(100),  
	STATE             char(3), 
	POSTCODE          number(4),
	EMPLOYED          number(8),
	UNEMPLOYED        number(8)
);

''')

fname = 'NSWEmploymentrate.csv'
fhand = open(fname)
xcount = 0

#######################################################################
### Populate NSW_BIRTH_RATE Table                                   ### 
#######################################################################
for line in fhand:	
	fields = line.split(',')

	YEAR      = fields[0].strip() 
	LOCALITY  = fields[1].strip()  
	SUBURB    = fields[2].strip() 
	STATE     = fields[3].strip() 
	POSTCODE  = fields[4].strip() 
	EMPLOYED  = fields[5].strip() 
	UNEMPLOYED = fields[6].strip()

	xcount = xcount+1

	if YEAR == "Year" : continue

	cur.execute('''INSERT INTO NSW_EMPLOYMENT_RATE
        (
		YEAR,
		LOCALITY,
		SUBURB,
		STATE,
		POSTCODE,
		EMPLOYED,
		UNEMPLOYED
        )  
        VALUES ( ?, ?, ?, ?, ?, ?, ?)''',   
		(
		YEAR,
		LOCALITY,
		SUBURB,
		STATE,
		POSTCODE,
		EMPLOYED,
		UNEMPLOYED
		))

conn.commit()

print ('Done')
print ('Total Records appended : ', xcount )
