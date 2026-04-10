from quant_alpha.analytics.greeks import bs_greeks_vectorized

def vanna_volga(S, K, T, r, sigma):
    _, _, vega, d1, d2 = bs_greeks_vectorized(S, K, T, r, sigma, True)
    vanna = vega * (1 - d1/(sigma*(T**0.5))) / S
    volga = vega * d1 * d2 / sigma
    return vanna, volga
