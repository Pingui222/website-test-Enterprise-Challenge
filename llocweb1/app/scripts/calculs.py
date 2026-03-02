# càlculs
def sumainterval(i,f):
    s = 0
    for v in range(i,f+1):
        s = s + v
    return s

def llegirfitxer(nomf):
    n = 'app/scripts/'+nomf
    print(n)
    with  open(n,'r') as f:
        d = f.read()
    return 'hola <br> bon dia <br><br>' + d

def mostrarllistat(nomf):
    ltot = []
    n = 'app/scripts/'+nomf
    with  open(n,'r') as f:
        for e in f:
            e = e[:-1]
            l = e.split(',')
            print(l)
            ltot.append(l)
    return ltot
