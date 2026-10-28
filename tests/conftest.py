import os
import sys

# Permite ejecutar pytest desde la raíz del proyecto (importa app y cargar_csv).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
