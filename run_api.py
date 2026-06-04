import uvicorn
import sys

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
            
    print(f"Iniciando API REST en el puerto {port}...")
    print(f"Documentación Swagger disponible en: http://localhost:{port}/docs")
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
