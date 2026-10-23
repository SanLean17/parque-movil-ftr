"""Version 7 technical attributes. None means not explicitly identified."""
INFORMATION = {
    'ubicacion': ('delantero','trasero','derecho','izquierdo','superior','inferior','interno','externo','zona media'),
    'parte': ('extremo','lado eje','lado pitman'),
    'subcomponente': ('diafragma',),
    'defecto': ('flojo','suelto','juego','corte','pinchadura','liso','faltante','no_funciona','rotura','desgaste'),
    'cantidad': ('dos',),
}
EXTRA_FIELDS = {'parte','subcomponente','cantidad_fisica','componente_asociado'}

def validate_extra(finding):
    if finding.get('parte') not in (None,*INFORMATION['parte']):raise ValueError('Parte del componente no confirmada.')
    if finding.get('subcomponente') not in (None,*INFORMATION['subcomponente']):raise ValueError('Subcomponente no confirmado.')
    quantity=finding.get('cantidad_fisica')
    if quantity is not None and (type(quantity) is not int or not 1<=quantity<=100):raise ValueError('Cantidad física no válida.')
    if finding.get('componente_asociado') not in (None,'pulmon_freno'):raise ValueError('Referencia de componente no confirmada.')
    if finding.get('componente_asociado') and finding['componente']!='flexibles_freno':raise ValueError('La referencia al pulmón corresponde al flexible de freno.')
    if finding.get('subcomponente')=='diafragma' and finding['componente']!='pulmon_freno':raise ValueError('Diafragma requiere confirmar el pulmón de freno.')
