# -*- coding: utf-8 -*-

# Copyright 2015 Mike Fährmann
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.

"""Methods to access sites behind Cloudflare protection"""

import time
import operator
import urllib.parse
from . import text

def bypass_ddos_protection(session, url):
    """Prepare a requests.session to access 'url' behind Cloudflare protection"""
    session.headers["Referer"] = url
    if url in _cache:
        session.cookies.update(_cache[url])
        return
    page = session.get(url).text
    params = text.extract_all(page, (
        ('jschl_vc', 'name="jschl_vc" value="', '"'),
        ('pass'    , 'name="pass" value="', '"'),
    ))[0]
    params["jschl_answer"] = solve_jschl(url, page)
    time.sleep(4)
    session.get(urllib.parse.urljoin(url, "/cdn-cgi/l/chk_jschl"), params=params)
    _cache[url] = session.cookies.copy()

def solve_jschl(url, page):
    """Solve challenge to get 'jschl_answer' value"""
    data, pos = text.extract_all(page, (
        ('var' , 'var t,r,a,f, ', '='),
        ('key' , '"', '"'),
        ('expr', ':', '}')
    ))
    solution = evaluate_expression(data["expr"])
    variable = "{}.{}".format(data["var"], data["key"])
    vlength = len(variable)
    expressions = text.extract(page, "'challenge-form');", "f.submit();", pos)[0]
    for expr in expressions.split(";")[1:]:
        if expr.startswith(variable):
            func = operator_functions[expr[vlength]]
            value = evaluate_expression(expr[vlength+2:])
            solution = func(solution, value)
        elif expr.startswith("a.value"):
            return solution + len(urllib.parse.urlparse(url).netloc)

def evaluate_expression(expr):
    """Evaluate a Javascript expression for the challange and return its value"""
    stack = []
    ranges = []
    value = ""
    for index, char in enumerate(expr):
        if char == "(":
            stack.append(index+1)
        elif char == ")":
            begin = stack.pop()
            if stack:
                ranges.append((begin, index))
    for subexpr in [expr[begin:end] for begin, end in ranges] or (expr,):
        num = 0
        for part in subexpr.split("[]"):
            num += expression_values[part]
        value += str(num)
    return int(value)

operator_functions = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
}

expression_values = {
    "": 0,
    "+": 0,
    "!+": 1,
    "+!!": 1,
}

_cache = {}
