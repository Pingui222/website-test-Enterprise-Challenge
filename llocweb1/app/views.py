# primer lloc web
# @app.route són les peticions que pot atendre el servidor

from flask import render_template
from app import app
from flask import request

#from app.scripts import calculs as cal

#from app.scripts.calculs import sumainterval
from .scripts.calculs import *

@app.route('/')
@app.route('/index')
def index():

    return render_template('index.html')

@app.route('/calcula', methods=['POST'])
def calcul():
    ini = request.form['vini']
    fi = request.form['vfin']
 
    # cridem a la funció que farà el càlcul de la suma entre ini i fi
    s = sumainterval(int(ini),int(fi))
    print(s)
 
    # en el return tornem les variables per separat, però es pot tornar un dict
    # amb els valors a tornar {'id':'valor'}
    return render_template('calcul.html',
                           title = 'sumainterval',
                           e1 = ini,
                           e2 = fi,
                           resultat = str(s))
@app.route('/sumavalors')
def suma():
    return render_template('sumav.html')

@app.route('/load')
def llegir():
    d = llegirfitxer('dades.csv')
    print(d)    
    return(d)

@app.route('/llistat')
def llistat():
    d = mostrarllistat('dades.csv')
    print(d)
    return render_template('dadeslist.html', 
                            lst = d)

@app.route('/cotxe', methods=['POST'])
def mostracotxe():
    sel= request.form['cars']
    print(sel)
    return render_template('cotxe.html',
                          selec = sel)

