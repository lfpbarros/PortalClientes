# client/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def last_key(dictionary_slice):
    """
    Retorna a última chave de um dicionário fatiado ou lista de chaves.
    Usado para navegação "Previous Step".
    """
    if isinstance(dictionary_slice, dict):
        return list(dictionary_slice.keys())[-1]
    elif isinstance(dictionary_slice, list):
        if dictionary_slice:
            return dictionary_slice[-1]
    return None

@register.filter
def replace(value, arg):
    """
    Substitui todas as ocorrências de uma string por outra.
    Uso: {{ value|replace:"old,new" }}
    """
    if isinstance(value, str) and isinstance(arg, str):
        old, new = arg.split(',', 1) # Divide em no máximo 2 partes: 'old' e 'new'
        return value.replace(old, new)
    return value