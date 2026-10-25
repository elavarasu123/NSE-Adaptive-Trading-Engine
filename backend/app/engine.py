from .market import DemoProvider
provider=DemoProvider()
SEEDS=[("TCS",84,68,21,11,"BUY"),("ICICIBANK",80,63,24,13,"WATCH"),("LT",76,59,27,14,"WATCH"),("RELIANCE",71,54,29,17,"WAIT"),("SBIN",65,47,31,22,"REJECT")]
def scan():
    out=[]
    for s,score,up,side,down,d in SEEDS:
        q=provider.quote(s)
        out.append({"symbol":s,"price":q.price,"score":score,"up":up,"sideways":side,"down":down,"decision":d,"stop":round(q.price*.94,2),"target":round(q.price*1.10,2)})
    return out
