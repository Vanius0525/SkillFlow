"""Same official scores, fresh latex parser globals before each TheoremQA answer."""
import copy
_INITIAL = None

def evaluate(text, item):
    if item.get('dataset','medcalcbench')=='medcalcbench':
        from howskill import grade
        return bool(grade.evaluate(text,item)['correct'])
    from howskill import sra_eval
    import latex2sympy2 as parser
    global _INITIAL
    fields=('var','variances','VARIABLE_VALUES','frac_type','is_real')
    if _INITIAL is None:
        _INITIAL={k:copy.deepcopy(getattr(parser,k)) for k in fields}
    for k,v in _INITIAL.items():setattr(parser,k,copy.deepcopy(v))
    return bool(sra_eval.evaluate(text,item)['correct'])
