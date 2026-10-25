from abc import ABC,abstractmethod
from datetime import datetime
from dataclasses import dataclass
import math
@dataclass
class Quote: symbol:str; price:float; change_pct:float; timestamp:datetime
class MarketDataProvider(ABC):
    @abstractmethod
    def quote(self,symbol): ...
class DemoProvider(MarketDataProvider):
    BASE={"TCS":3185,"ICICIBANK":1390,"LT":3720,"RELIANCE":1420,"SBIN":905}
    def quote(self,symbol):
        base=self.BASE.get(symbol.upper(),1000); drift=math.sin(datetime.utcnow().minute/8)*.006
        return Quote(symbol.upper(),round(base*(1+drift),2),round(drift*100,2),datetime.utcnow())
