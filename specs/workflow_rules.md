# Workflow Rules (Spec-Driven Development)

1. **La especificación manda**: Cada cambio mayor debe verse reflejado primero en la documentación y los specs.
2. **Commits descriptivos**: Usar convención `feat:`, `fix:`, `chore:`, `docs:`.
3. **Persistencia**: La herramienta no modifica los Excel originales hasta la fase final (exportación). Todos los datos temporales viven en JSONs o DataFrames intermedios.
4. **Respeto a límites de API**: Los conectores LLM deben implementar backoff exponencial.
5. **Seguridad**: No subir bajo ninguna circunstancia credenciales en archivos locales como `.env` ni OAuth tokens.
