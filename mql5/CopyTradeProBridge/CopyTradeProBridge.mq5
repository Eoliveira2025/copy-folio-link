//+------------------------------------------------------------------+
//|                                       CopyTradeProBridge.mq5     |
//|  EA for the MASTER account: detects OPEN/CLOSE/MODIFY events and |
//|  forwards them to CopyTrade Pro via HTTPS.                        |
//+------------------------------------------------------------------+
#property copyright "CopyTrade Pro"
#property version   "1.00"
#property strict

input string  API_URL       = "https://your-domain.com/api/v1/bridge/signal";
input string  API_TOKEN     = "change-me";
input string  MASTER_ID     = "low-master-01";
input string  STRATEGY_ID   = "";          // optional UUID
input int     TIMER_MS      = 250;          // polling interval in ms
input bool    SEND_BALANCE  = true;

struct PosSnap {
   ulong  ticket;
   string symbol;
   int    type;
   double volume;
   double price;
   double sl;
   double tp;
};

PosSnap g_prev[];

//+------------------------------------------------------------------+
int OnInit() {
   EventSetMillisecondTimer(TIMER_MS);
   SnapshotPositions(g_prev);
   PrintFormat("[CopyTradeProBridge] Initialized. master=%s positions=%d", MASTER_ID, ArraySize(g_prev));
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { EventKillTimer(); }

//+------------------------------------------------------------------+
void SnapshotPositions(PosSnap &out[]) {
   ArrayResize(out, 0);
   int total = PositionsTotal();
   for(int i=0; i<total; i++) {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(!PositionSelectByTicket(ticket)) continue;
      PosSnap s;
      s.ticket = ticket;
      s.symbol = PositionGetString(POSITION_SYMBOL);
      s.type   = (int)PositionGetInteger(POSITION_TYPE);
      s.volume = PositionGetDouble(POSITION_VOLUME);
      s.price  = PositionGetDouble(POSITION_PRICE_OPEN);
      s.sl     = PositionGetDouble(POSITION_SL);
      s.tp     = PositionGetDouble(POSITION_TP);
      int n = ArraySize(out);
      ArrayResize(out, n+1);
      out[n] = s;
   }
}

int FindByTicket(const PosSnap &arr[], ulong ticket) {
   for(int i=0; i<ArraySize(arr); i++) if(arr[i].ticket == ticket) return i;
   return -1;
}

string OrderTypeStr(int t) {
   switch(t) {
      case POSITION_TYPE_BUY:  return "BUY";
      case POSITION_TYPE_SELL: return "SELL";
   }
   return "UNKNOWN";
}

//+------------------------------------------------------------------+
void SendSignal(string action, const PosSnap &p) {
   string balance = SEND_BALANCE ? DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) : "null";
   string body = StringFormat(
      "{\"master_id\":\"%s\",\"strategy_id\":%s,\"action\":\"%s\",\"symbol\":\"%s\","
      "\"order_type\":\"%s\",\"volume\":%s,\"price\":%s,\"sl\":%s,\"tp\":%s,"
      "\"master_ticket\":\"%I64u\",\"position_id\":\"%I64u\",\"master_balance\":%s}",
      MASTER_ID,
      (StringLen(STRATEGY_ID) > 0 ? "\"" + STRATEGY_ID + "\"" : "null"),
      action, p.symbol, OrderTypeStr(p.type),
      DoubleToString(p.volume, 2),
      DoubleToString(p.price, _Digits),
      DoubleToString(p.sl, _Digits),
      DoubleToString(p.tp, _Digits),
      p.ticket, p.ticket, balance
   );

   if(StringLen(API_TOKEN) == 0) { Print("[Bridge] API_TOKEN missing"); return; }

   char post[]; StringToCharArray(body, post, 0, StringLen(body));
   char result[]; string headers = "Content-Type: application/json\r\nAuthorization: Bearer " + API_TOKEN + "\r\n";
   string resp_headers;
   ResetLastError();
   int code = WebRequest("POST", API_URL, headers, 5000, post, result, resp_headers);
   if(code == -1) {
      PrintFormat("[Bridge] WebRequest error %d. Allow URL in Tools>Options>Expert Advisors.", GetLastError());
      return;
   }
   PrintFormat("[Bridge] %s %s vol=%.2f http=%d", action, p.symbol, p.volume, code);
}

//+------------------------------------------------------------------+
void OnTimer() {
   PosSnap curr[];
   SnapshotPositions(curr);

   // Detect OPEN / MODIFY
   for(int i=0; i<ArraySize(curr); i++) {
      int idx = FindByTicket(g_prev, curr[i].ticket);
      if(idx == -1) {
         SendSignal("OPEN", curr[i]);
      } else {
         PosSnap p = g_prev[idx];
         if(MathAbs(p.sl - curr[i].sl) > _Point/2 ||
            MathAbs(p.tp - curr[i].tp) > _Point/2 ||
            MathAbs(p.volume - curr[i].volume) > 1e-6) {
            SendSignal("MODIFY", curr[i]);
         }
      }
   }
   // Detect CLOSE
   for(int i=0; i<ArraySize(g_prev); i++) {
      if(FindByTicket(curr, g_prev[i].ticket) == -1) {
         SendSignal("CLOSE", g_prev[i]);
      }
   }

   ArrayResize(g_prev, 0);
   for(int i=0; i<ArraySize(curr); i++) {
      int n = ArraySize(g_prev);
      ArrayResize(g_prev, n+1);
      g_prev[n] = curr[i];
   }
}
