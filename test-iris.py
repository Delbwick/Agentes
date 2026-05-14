#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EJECUTOR RÁPIDO - ANALIZADOR DE DATOS FINANCIEROS
Script de conveniencia para ejecutar el analizador fácilmente
"""

import os
import sys
import subprocess
from pathlib import Path

def mostrar_menu():
    """Muestra el menú principal"""
    os.system('clear' if os.name != 'nt' else 'cls')
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║    📊 ANALIZADOR DE DATOS FINANCIEROS - MENÚ PRINCIPAL         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

    1️⃣  Ejecutar análisis de archivo CSV (Python)
    2️⃣  Abrir visualizador web interactivo (Navegador)
    3️⃣  Ver ejemplo de datos
    4️⃣  Instalar dependencias necesarias
    5️⃣  Leer documentación
    6️⃣  Salir

    Selecciona una opción (1-6): """)


def ejecutar_analisis_python():
    """Ejecuta el analizador en Python"""
    script_path = Path(__file__).parent / "analizador_datos_financieros.py"
    
    if not script_path.exists():
        print("\n❌ Error: No se encuentra analizador_datos_financieros.py")
        input("\nPresiona Enter para continuar...")
        return
    
    try:
        # Verificar que pandas esté instalado
        import pandas
    except ImportError:
        print("\n⚠️  Se requiere instalar pandas")
        print("Ejecutando: pip install pandas numpy...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pandas", "numpy", "-q"])
    
    print("\n" + "="*70)
    print("Ejecutando analizador Python...\n")
    subprocess.run([sys.executable, str(script_path)])


def abrir_visualizador():
    """Abre el visualizador web"""
    html_path = Path(__file__).parent / "analizador_visualizador.html"
    
    if not html_path.exists():
        print("\n❌ Error: No se encuentra analizador_visualizador.html")
        input("\nPresiona Enter para continuar...")
        return
    
    try:
        import webbrowser
        webbrowser.open(f'file://{html_path.absolute()}')
        print(f"\n✅ Abriendo navegador...")
        print(f"   Si no se abre automáticamente, copia esta ruta en tu navegador:")
        print(f"   {html_path.absolute()}")
    except Exception as e:
        print(f"\n⚠️  No se pudo abrir automáticamente: {e}")
        print(f"   Abre manualmente el archivo:")
        print(f"   {html_path.absolute()}")
    
    input("\n\nPresiona Enter cuando termines...")


def mostrar_ejemplo():
    """Muestra el archivo de ejemplo"""
    csv_path = Path(__file__).parent / "ejemplo_datos_financieros.csv"
    
    if not csv_path.exists():
        print("\n❌ Error: No se encuentra archivo de ejemplo")
        input("\nPresiona Enter para continuar...")
        return
    
    os.system('clear' if os.name != 'nt' else 'cls')
    print("\n📋 ARCHIVO DE EJEMPLO: ejemplo_datos_financieros.csv\n")
    print("="*70)
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
            print(contenido)
    except:
        print("❌ Error al leer el archivo")
    
    print("\n" + "="*70)
    input("\nPresiona Enter para continuar...")


def instalar_dependencias():
    """Instala las dependencias necesarias"""
    print("\n📦 Instalando dependencias necesarias...")
    print("   - pandas")
    print("   - numpy\n")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "pandas", "numpy"], 
                      capture_output=False)
        print("\n✅ Dependencias instaladas correctamente")
    except Exception as e:
        print(f"\n❌ Error al instalar: {e}")
        print("   Intenta ejecutar manualmente:")
        print("   pip install pandas numpy")
    
    input("\nPresiona Enter para continuar...")


def mostrar_documentacion():
    """Muestra la documentación"""
    readme_path = Path(__file__).parent / "README.md"
    
    if not readme_path.exists():
        print("\n❌ Error: No se encuentra README.md")
        input("\nPresiona Enter para continuar...")
        return
    
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            contenido = f.read()
            
        # Mostrar contenido por partes
        os.system('clear' if os.name != 'nt' else 'cls')
        print(contenido)
        
    except Exception as e:
        print(f"\n❌ Error al leer documentación: {e}")
    
    input("\nPresiona Enter para continuar...")


def main():
    """Función principal"""
    while True:
        mostrar_menu()
        
        opcion = input().strip()
        
        if opcion == "1":
            ejecutar_analisis_python()
        elif opcion == "2":
            abrir_visualizador()
        elif opcion == "3":
            mostrar_ejemplo()
        elif opcion == "4":
            instalar_dependencias()
        elif opcion == "5":
            mostrar_documentacion()
        elif opcion == "6":
            print("\n👋 ¡Hasta pronto!\n")
            sys.exit(0)
        else:
            print("\n❌ Opción inválida. Intenta de nuevo.")
            input("Presiona Enter para continuar...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Programa interrumpido por el usuario")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        sys.exit(1)
