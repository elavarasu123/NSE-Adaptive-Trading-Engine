from fastapi import FastAPI,Depends,HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import Base,engine,SessionLocal,get_db
from .models import Portfolio,Position,Prediction,Journal
from .engine import scan,provider
from .risk import position_size
Base.metadata.create_all(engine)
app=FastAPI(title="NSE Adaptive Trading Engine",version="0.1")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])
db=SessionLocal()
if not db.query(Portfolio).first():
    db.add(Portfolio(initial_capital=100000,cash=100000)); db.add(Journal(kind="SYSTEM",message="Initialized one-time ₹1,00,000 paper capital.")); db.commit()
db.close()
@app.get("/health")
def health(): return {"status":"ok","mode":"PAPER","provider":"DEMO","tickByTick":False}
@app.get("/api/dashboard")
def dashboard(db:Session=Depends(get_db)):
    p=db.query(Portfolio).first(); pos=db.query(Position).filter(Position.status=="OPEN").all()
    mv=sum(x.quantity*x.current_price for x in pos); cost=sum(x.quantity*x.avg_price for x in pos)
    return {"portfolio":{"initialCapital":p.initial_capital,"cash":round(p.cash,2),"invested":round(mv,2),"value":round(p.cash+mv,2),"pnl":round(p.realized_pnl+mv-cost,2)},"engine":{"status":"ONLINE","strategy":"champion-v1","regime":"NEUTRAL"},"positions":[{"symbol":x.symbol,"quantity":x.quantity,"entry":x.avg_price,"current":x.current_price,"stop":x.stop_price,"target":x.target_price} for x in pos]}
@app.get("/api/candidates")
def candidates(): return scan()
@app.post("/api/engine/run")
def run(db:Session=Depends(get_db)):
    rows=scan()
    for c in rows: db.add(Prediction(symbol=c["symbol"],up=c["up"]/100,sideways=c["sideways"]/100,down=c["down"]/100,confidence=c["score"]/100,decision=c["decision"],evidence="V0.1 demo feature stack"))
    db.add(Journal(kind="SCAN",message=f"Frozen {len(rows)} predictions.")); db.commit()
    return {"status":"complete","predictionsFrozen":len(rows)}
@app.get("/api/predictions")
def predictions(db:Session=Depends(get_db)):
    r=db.query(Prediction).order_by(Prediction.created_at.desc()).limit(100).all()
    return [{"id":x.id,"symbol":x.symbol,"createdAt":x.created_at,"horizon":x.horizon,"up":x.up,"sideways":x.sideways,"down":x.down,"confidence":x.confidence,"decision":x.decision,"status":x.status,"version":x.version} for x in r]
@app.post("/api/paper/buy/{symbol}")
def buy(symbol:str,db:Session=Depends(get_db)):
    symbol=symbol.upper(); p=db.query(Portfolio).first()
    if db.query(Position).filter(Position.symbol==symbol,Position.status=="OPEN").first(): raise HTTPException(400,"Already open")
    q=provider.quote(symbol); stop=round(q.price*.94,2); target=round(q.price*1.10,2); qty=position_size(p.cash,q.price,stop)
    if qty<1: raise HTTPException(400,"Risk gate rejected")
    p.cash-=qty*q.price; db.add(Position(symbol=symbol,quantity=qty,avg_price=q.price,current_price=q.price,stop_price=stop,target_price=target)); db.add(Journal(kind="PAPER_BUY",message=f"{symbol} {qty} @ ₹{q.price}")); db.commit()
    return {"symbol":symbol,"quantity":qty,"entry":q.price,"stop":stop,"target":target}
