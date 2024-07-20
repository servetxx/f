import ccxt
import pandas as pd
import pandas_ta as ta
from datetime import datetime
import time

# Binance API key
API_KEY = "Jjin5M9cYG8TQuZBksuhsLzfjuHadt5RCqyU0UN7FnC59MyWMhRXo6SXcG3CPCna"
API_SECRET = "Xw9MmLHhs2qVP1ABgNt9gZ515SHIynIoCKU2gPBDeuqC3D4Dqa0RCFnQPpnN6s6C"

# Binance borsasına bağlan (API key ile)
exchange = ccxt.binance({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

# RSI hesaplama
def calculate_rsi(closes, window=14):
    df = pd.DataFrame(closes, columns=['close'])
    if len(df) < window:
        return None  # Yeterli veri yoksa None döndür
    rsi = df.ta.rsi(length=window)
    return rsi.iloc[-1] if not rsi.empty else None

# Mevcut bakiyeyi al
def get_balance():
    balance = exchange.fetch_balance()
    return balance

# Alım emri gönder
def place_market_buy_order(symbol, amount_usdt):
    try:
        ticker = exchange.fetch_ticker(symbol)
        amount_coin = amount_usdt / ticker['last']
        order = exchange.create_market_buy_order(symbol, amount_coin)
        print(f"{datetime.now()} - Alım emri başarıyla gönderildi. Alınan miktar: {amount_coin} {symbol.split('/')[0]}")
        return order
    except Exception as e:
        print(f"{datetime.now()} - Alım emri gönderilirken hata oluştu: {e}")
        return None

# Satım emri gönder
def place_market_sell_order(symbol, amount_coin):
    try:
        order = exchange.create_market_sell_order(symbol, amount_coin)
        print(f"{datetime.now()} - Satım emri başarıyla gönderildi. Satılan miktar: {amount_coin} {symbol.split('/')[0]}")
        return order
    except Exception as e:
        print(f"{datetime.now()} - Satım emri gönderilirken hata oluştu: {e}")
        return None

# Binance'den fiyat verilerini çek
def fetch_ticker(symbol):
    try:
        ticker = exchange.fetch_ticker(symbol)
        return ticker['last']
    except Exception as e:
        print(f"Veri çekilirken hata oluştu: {e}")
        return None

# Binance'den 1 dakikalık verileri çek
def fetch_ohlcv(symbol, timeframe='1m', limit=100):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        print(f"Veri çekildi: {len(data)} mum")
        return data
    except Exception as e:
        print(f"Veri çekilirken hata oluştu: {e}")
        return []

# Ana işlem döngüsü
def main(symbols, quote_currency, take_profit_pct, stop_loss_pct, cooldown_period):
    symbol_states = {symbol: {'rsi_triggered': False, 'buy_price': None, 'sold_out': False, 'cooldown': False} for symbol in symbols}

    while True:
        balance = get_balance()
        quote_balance = balance['total'][quote_currency]

        for symbol in symbols:
            base_currency = symbol.split('/')[0]
            base_balance = balance['total'][base_currency]
            symbol_state = symbol_states[symbol]

            if symbol_state['cooldown']:
                continue  # Bekleme süresi devam ediyorsa bu sembolü atla

            # Anlık fiyatı al
            current_price = fetch_ticker(symbol)
            if current_price is None:
                time.sleep(60)
                continue

            # 1 dakikalık verileri çek
            ohlcv = fetch_ohlcv(symbol, timeframe='1m', limit=100)
            closes = [x[4] for x in ohlcv]  # Kapanış fiyatlarını al

            # RSI hesapla
            rsi = calculate_rsi(closes)

            print(f"\n{datetime.now()} - {symbol} Güncel Fiyat: {current_price}")
            print(f"RSI: {rsi}")

            # RSI sinyalini kontrol et ve alım yap
            if rsi is not None and rsi < 25 and not symbol_state['rsi_triggered']:
                amount_quote = quote_balance / len(symbols)  # Her sembole eşit miktar ayır
                order = place_market_buy_order(symbol, amount_quote)
                if order:
                    symbol_state['buy_price'] = current_price  # Alış fiyatını kaydet
                    symbol_state['rsi_triggered'] = True  # RSI tetiklemesini ayarla

            # Take-profit ve stop-loss kontrolü
            if symbol_state['buy_price']:
                if current_price >= symbol_state['buy_price'] * (1 + take_profit_pct):
                    if base_balance > 0:
                        order = place_market_sell_order(symbol, base_balance)
                        if order:
                            symbol_state['buy_price'] = None  # Alış fiyatını sıfırla
                            symbol_state['rsi_triggered'] = False  # RSI tetiklemesini sıfırla
                            symbol_state['sold_out'] = False  # Satış başarılı, sold_out bayrağını sıfırla
                            symbol_state['cooldown'] = True  # Bekleme süresini başlat
                        print(f"{datetime.now()} - {symbol} Take-profit tetiklendi. Fiyat: {current_price}")
                    else:
                        if not symbol_state['sold_out']:
                            print(f"{datetime.now()} - {symbol} için yeterli {base_currency} bakiyesi yok.")
                            symbol_state['sold_out'] = True  # Satış yapılamadı, sold_out bayrağını ayarla

                elif current_price <= symbol_state['buy_price'] * (1 - stop_loss_pct):
                    if base_balance > 0:
                        order = place_market_sell_order(symbol, base_balance)
                        if order:
                            symbol_state['buy_price'] = None  # Alış fiyatını sıfırla
                            symbol_state['rsi_triggered'] = False  # RSI tetiklemesini sıfırla
                            symbol_state['sold_out'] = False  # Satış başarılı, sold_out bayrağını sıfırla
                            symbol_state['cooldown'] = True  # Bekleme süresini başlat
                        print(f"{datetime.now()} - {symbol} Stop-loss tetiklendi. Fiyat: {current_price}")
                    else:
                        if not symbol_state['sold_out']:
                            print(f"{datetime.now()} - {symbol} için yeterli {base_currency} bakiyesi yok.")
                            symbol_state['sold_out'] = True  # Satış yapılamadı, sold_out bayrağını ayarla

        # Bekleme süresini kontrol et ve gerektiğinde sıfırla
        for symbol in symbols:
            if symbol_states[symbol]['cooldown']:
                time.sleep(cooldown_period)
                symbol_states[symbol]['cooldown'] = False

        # Her 1 dakikada bir işlem yap
        time.sleep(15)

if __name__ == "__main__":
    symbols = ["BAKE/USDT", "BNX/USDT", "XRP/USDT", "PEOPLE/USDT", "1000SATS/USDT", "NOT/USDT", "COS/USDT"]  # İşlem yapmak istediğiniz coin çiftleri
    quote_currency = "USDT"  # Referans para birimi
    take_profit_pct = 0.032  # %3.2 kar
    stop_loss_pct = 0.013  # %1.3 stop-loss
    cooldown_period = 60 * 5  # 5 dakika bekleme süresi
    main(symbols, quote_currency, take_profit_pct, stop_loss_pct, cooldown_period)
