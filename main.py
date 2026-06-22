from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sympy as sp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class RequisitosNegocio(BaseModel):
    clientes_base: int
    clientes_peak: int
    horas_peak: int 
    tiene_segundo_peak: bool = False
    clientes_peak2: int = 0
    horas_peak2: int = 0
    quiere_buckets: bool
    region: str              
    base_datos_gb: int       
    quiere_load_balancer: bool

# --- CATÁLOGO REAL Y COMPLETO DE LAS NUBES ---
def obtener_instancia_real(nube, cores_necesarios, ram_necesaria):
    catalogo = {
        "AWS": [
            {"nombre": "t3.micro", "cores": 2, "ram": 1},
            {"nombre": "t3.small", "cores": 2, "ram": 2},
            {"nombre": "t3.medium", "cores": 2, "ram": 4},
            {"nombre": "t3.large", "cores": 2, "ram": 8},
            {"nombre": "t3.xlarge", "cores": 4, "ram": 16},
            {"nombre": "t3.2xlarge", "cores": 8, "ram": 32},
            {"nombre": "m5.4xlarge", "cores": 16, "ram": 64},
            {"nombre": "m5.8xlarge", "cores": 32, "ram": 128},
            {"nombre": "m5.24xlarge", "cores": 96, "ram": 384}
        ],
        "GCP": [
            {"nombre": "e2-micro", "cores": 2, "ram": 1},
            {"nombre": "e2-small", "cores": 2, "ram": 2},
            {"nombre": "e2-medium", "cores": 2, "ram": 4},
            {"nombre": "e2-standard-2", "cores": 2, "ram": 8},
            {"nombre": "e2-standard-4", "cores": 4, "ram": 16},
            {"nombre": "e2-standard-8", "cores": 8, "ram": 32},
            {"nombre": "e2-standard-16", "cores": 16, "ram": 64},
            {"nombre": "e2-standard-32", "cores": 32, "ram": 128},
            {"nombre": "n2-standard-80", "cores": 80, "ram": 320}
        ],
        "Azure": [
            {"nombre": "Standard_B1s", "cores": 1, "ram": 1},
            {"nombre": "Standard_B2s", "cores": 2, "ram": 4},
            {"nombre": "Standard_D2s_v3", "cores": 2, "ram": 8},
            {"nombre": "Standard_D4s_v3", "cores": 4, "ram": 16},
            {"nombre": "Standard_D8s_v3", "cores": 8, "ram": 32},
            {"nombre": "Standard_D16s_v3", "cores": 16, "ram": 64},
            {"nombre": "Standard_D32s_v3", "cores": 32, "ram": 128},
            {"nombre": "Standard_D64s_v3", "cores": 64, "ram": 256}
        ]
    }
    
    # El bucle busca la instancia más barata que soporte los requerimientos
    for instancia in catalogo[nube]:
        if instancia["cores"] >= cores_necesarios and instancia["ram"] >= ram_necesaria:
            return instancia["nombre"]
            
    return "Clúster (Autoescalado masivo)"
# ---------------------------------------------

@app.get("/")
def mostrar_interfaz():
    return FileResponse("index.html")

@app.post("/calcular-nube")
def calcular_costos(req: RequisitosNegocio):
    t = sp.Symbol('t')
    B = req.clientes_base
    P1 = req.clientes_peak
    H1 = req.horas_peak

    # --- MODELO MATEMÁTICO POR TRAMOS (CÁLCULO 1) ---
    if not req.tiene_segundo_peak:
        a1 = (P1 - B) / (H1**2) if H1 > 0 else 0
        T = -a1 * (t - H1)**2 + P1
        T_prima = sp.diff(T, t)
        usuarios_maximos = P1
        tasa_crecimiento = T_prima.subs(t, max(0, H1 - 1))
    else:
        P2 = req.clientes_peak2
        H2 = req.horas_peak2
        
        if H1 > H2:
            H1, H2 = H2, H1
            P1, P2 = P2, P1
            
        M = (H1 + H2) / 2
        
        a1 = (P1 - B) / (H1**2) if H1 > 0 else 0
        T1 = -a1 * (t - H1)**2 + P1
        
        T1_en_M = T1.subs(t, M)
        denom = (M - H2)**2
        a2 = (P2 - T1_en_M) / denom if denom != 0 else 0
        T2 = -a2 * (t - H2)**2 + P2
        
        T = sp.Piecewise((T1, t <= M), (T2, t > M))
        T_prima = sp.diff(T, t)
        
        usuarios_maximos = max(P1, P2, float(T1_en_M))
        
        tasa1 = sp.diff(T1, t).subs(t, max(0, H1 - 1))
        tasa2 = sp.diff(T2, t).subs(t, max(M, H2 - 1))
        tasa_crecimiento = max(abs(tasa1), abs(tasa2))

    nucleos_necesarios = max(1, int(usuarios_maximos / 500))
    ram_necesaria = nucleos_necesarios * 2
    recomienda_autoscaling = tasa_crecimiento > 100 

    # --- PROBLEMA DE OPTIMIZACIÓN (MÍNIMOS) ---
    max_peak_visto = max(P1, req.clientes_peak2) if req.tiene_segundo_peak else P1
    x = sp.Symbol('x', positive=True) 
    C_total = 0.1 * x + (max_peak_visto * 5000) / x
    C_prima = sp.diff(C_total, x)
    solucion_optima = sp.solve(C_prima, x)
    
    usuarios_optimos = float(solucion_optima[0]) if solucion_optima else max_peak_visto
    servidores_fijos_optimos = max(1, round(usuarios_optimos / 500))

    # --- TARIFAS COMERCIALES ---
    multiplicadores = {"us": 1.0, "eu": 1.15, "sa": 1.3}
    factor_region = multiplicadores.get(req.region, 1.0)

    precios = {
        "AWS": {"core": 10.0, "ram": 2.0, "db_gb": 0.25}, 
        "GCP": {"core": 9.0,  "ram": 1.8, "db_gb": 0.22},
        "Azure": {"core": 11.0, "ram": 2.2, "db_gb": 0.28},
    }
    
    costo_bucket = 5.0 if req.quiere_buckets else 0.0
    costo_autoscaling = 10.0 if recomienda_autoscaling else 0.0
    costo_lb = 15.0 if req.quiere_load_balancer else 0.0 

    estimacion_detallada = {}
    for cloud, data_cloud in precios.items():
        core_cost = (nucleos_necesarios * data_cloud["core"]) * factor_region
        ram_cost = (ram_necesaria * data_cloud["ram"]) * factor_region
        db_cost = req.base_datos_gb * data_cloud["db_gb"]
        total = core_cost + ram_cost + costo_bucket + costo_autoscaling + costo_lb + db_cost
        
        # Llamamos al catálogo completo que restauramos arriba
        nombre_instancia = obtener_instancia_real(cloud, nucleos_necesarios, ram_necesaria)
        
        estimacion_detallada[cloud] = {
            "Instancia": nombre_instancia,
            "Cores": round(core_cost, 2), "RAM": round(ram_cost, 2),
            "Bucket": round(costo_bucket, 2), "Autoescalado": round(costo_autoscaling, 2),
            "LoadBalancer": round(costo_lb, 2), "BaseDatos": round(db_cost, 2),
            "Total": round(total, 2)
        }

    return {
        "recursos_requeridos": {
            "cpu_cores": nucleos_necesarios, "ram_gb": ram_necesaria, "usuarios_maximos": int(usuarios_maximos)
        },
        "estimacion_mensual": estimacion_detallada,
        "optimizacion": {
            "ecuacion_costo": str(C_total),
            "derivada_costo": str(C_prima),
            "usuarios_equilibrio": int(usuarios_optimos),
            "servidores_recomendados": int(servidores_fijos_optimos)
        }
    }