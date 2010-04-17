import logging
import re

from django.utils.encoding import smart_unicode
from django.utils.text import unescape_string_literal
from django.utils.translation import ugettext_lazy as _


class VariableDoesNotExist(Exception):
    pass


class Lexer(object):
    """
    A simple regular expression based tokenizer, it takes an origin string and
    outputs it's tokens. Since we use the re.findall method each Lexer maintains
    the state of were all the
    """
    tokenizer = re.compile(r"""
        \s*((?:\d+) # Literal number.
           # Literal string regex comes from the Mastering Regular Expressions book
           # and it's optimized for python NDA regex engine.
           |(?:'(?:[^'\\]*(?:\\.[^'\\]*)*)') # Literal single quote string.
           |(?:"(?:[^"\\]*(?:\\.[^"\\]*)*)") # Literal double quote string.
           |(?:[\w_\.]+) # Variables.
           |(?:\(|\)) # Parenthesis.
           |(?:[^\w\d \(\)]+)) # Operators.
        """, re.X)

    def __init__(self, origin):
        self.origin = origin

    def tokenize(self):
        "Return a list of tokens from a given expression"
        return self.tokenizer.findall(self.origin)


class Parser(object):
    """
    A Top down parser with operator precedence. It takes a list of tokens as
    parameter to the constructor and output an AST made of Symbols as a result
    of parsing.
    It's a recursive descendant parser that uses a 'binding power' to
    determine wether a token should be grabbed by the one on his left or on
    his right, allowing the parsing to be controlled by the Symbols themselves,
    rather than by the parsing algorithm, allowing a greater customization.
    """

    # It is inspired on the parser described in chapter 9 of Beautiful Code,
    # 1st edition. It is called Top Down Operator Precedence Parser and was
    # invented by Vaughan Pratt,
    # For more info there is an early version of the book chapter available on
    # http://javascript.crockford.com/tdop/tdop.html

    # To allow all operators to be dynamic there is this table.
    symbol_table = {}

    # Special end symbol, used when the tokens end
    end_symbol = None

    # Symbol to be yielded when a token is not found on symbol_table
    variable_symbol = None

    @staticmethod
    def register(name, klass):
        Parser.symbol_table[name] = klass

    def __init__(self, lexer):
        # Using a list instead of an iterator is easier here.
        self.tokens = lexer.tokenize()
        self.token_nr = 0;
        self.advance()

    def result(self):
        return self.expression()

    def expression(self, right_binding_power=0):
        """
        This is the heart of the parser. It takes a right binding power that
        determines how aggressively it should consume tokens that comes from
        the right of the expression.
        """
        previous_symbol = self.current_symbol
        self.advance()
        left = previous_symbol.nud()

        while right_binding_power < self.current_symbol.left_binding_power:
            previous_symbol = self.current_symbol
            self.advance()
            left = previous_symbol.led(left)

        return left

    def advance(self, token=None):
        """
        Get the class for the next token, or the end token.
        """
        if (Parser.symbol_table.get(token) and
            not isinstance(self.current_symbol, Parser.symbol_table.get(token))):
            raise SyntaxError(_("Expected token %s got %s")
                               % (token, self.tokens[self.token_nr]))

        if self.token_nr >= len(self.tokens):
            self.current_symbol = Parser.end_symbol
            return

        self.current_symbol = self.get_symbol(self.tokens[self.token_nr])
        self.token_nr += 1

        return self.current_symbol

    def get_symbol(self, token):
        """
        Try to get the operator of the token. If the token is not an operator,
        then it's a variable and will be returned.
        """
        symbol = Parser.symbol_table.get(token)

        if not symbol:
            symbol = Parser.variable_symbol

        return symbol(self, token)


class SymbolBase(type):
    """
    Metaclass for all symbols.

    Convenience class so you don't have to register all symbols manually.
    In the future it will be used to provide more info to the expression builder.
    """
    def __new__(cls, name, bases, attrs):
        klass = super(SymbolBase, cls).__new__(cls, name, bases, attrs)

        klass.left_binding_power = max(klass.precedence, klass.left_binding_power)

        if getattr(klass, "name", None):
            if not isinstance(klass.name, (tuple, list)):
                klass.name = [klass.name]

            for op_name in klass.name:
                if ' ' not in op_name:
                    Parser.register(op_name, klass)
                else:
                    # Would break the parser.
                    logging.error("Invalid operator [%s] for class %s. No spaces"
                                  " in operator names. Use underscore."
                                  % (op_name, name))

        return klass


class Symbol(object):
    """
    A symbol is a token on the tokenizer. It could be an operator or a variable.
    All symbols must inherit from this one, since the metaclass registers it.
    """
    __metaclass__ = SymbolBase

    name = None

    # Precedence varies from lowest to highest, 0 to 100.
    precedence = 0

    # Left binding power. The same as precedence.
    left_binding_power = 0

    # The parser constructs and owns the symbols.
    def __init__(self, parser, originating_token):
        self.token = originating_token
        self.parser = parser
        self.first = None
        self.second = None

    def __repr__(self):
        return "(%s %s %s)" % (self.token, self.first, self.second)

    def led(self, left):
        """
        A led indicates that the symbol cares about tokens on its left.
        The higher left_binding_power the higher will this symbol consume
        the one on its left.
        """
        raise SyntaxError(_("Token does not have a left denotation."))

    def nud(self):
        """
        A nud indicates that the symbol does not care about tokes to his
        left, and therefore is either an suffix operator or a variable.
        """
        raise SyntaxError(_("Token does not have a null denotation."))

    def resolve(self, context):
        raise SyntaxError(_("Abstract token. Can not be resolved."))

    def left(self, context):
        """Returns the token to the left of the this one."""
        return self.first.resolve(context)

    def right(self, context):
        """Returns the token to the right of the this one."""
        return self.second.resolve(context)


class Variable(Symbol):
    """
    A variable, resolvable against a given context. The variable may be
    a hard-coded string (if it begins and ends with single or double quote
    marks), a hard coded number or a name, with separator '.' .
    This is a modified version of Django's own Variable for templates.
    """

    name = "(==variable==)"

    # Necessary for defining the variable.
    def nud(self):
        return self

    def __init__(self, parser, originating_token):
        self.var = originating_token
        self.literal = None
        self.lookups = None

        try:
            # First try to treat this variable as a number.
            #
            # Note that this could cause an OverflowError here that we're not
            # catching. Since this should only happen at compile time, that's
            # probably OK.
            self.literal = float(self.var)

            # So it's a float... is it an int? If the original value contained a
            # dot or an "e" then it was a float, not an int.
            if '.' not in self.var and 'e' not in self.var.lower():
                self.literal = int(self.literal)

            # "2." is invalid
            if self.var.endswith('.'):
                raise ValueError
        except ValueError:
            # A ValueError means that the variable isn't a number.
            # If it's wrapped with quotes (single or double), then
            # we're also dealing with a literal.
            try:
                self.literal = unescape_string_literal(self.var)
            except ValueError:
                # Otherwise we'll set self.lookups so that resolve() knows we're
                # dealing with a bona fide variable
                self.lookups = tuple(self.var.split('.'))

    def resolve(self, context):
        """Resolve this variable against a given context."""
        if self.lookups is not None:
            # We're dealing with a variable that needs to be resolved
            value = self._resolve_lookup(context)
        else:
            # We're dealing with a literal, so it's already been "resolved"
            value = self.literal

        return value

    def __repr__(self):
        return "(variable %s)" % self.var

    def _resolve_lookup(self, context):
        """
        Performs resolution of a real variable (i.e. not a literal) against the
        given context.

        As indicated by the method's name, this method is an implementation
        detail and shouldn't be called by external code.
        """
        current = context

        for bit in self.lookups:
            try:
                # Dictionary lookup.
                current = current[bit]
            except (TypeError, AttributeError, KeyError):
                try:
                    # Attribute lookup.
                    current = getattr(current, bit)

                    if callable(current):
                        try:
                            # Method call (assuming no args required).
                            current = current()
                        except Exception:
                            # Arguments *were* required
                            # GOTCHA: This will also catch any TypeError.
                            # Raised in the function itself.
                            current = '' # Invalid method call.
                except (TypeError, AttributeError):
                    try:
                        # List-index lookup.
                        current = current[int(bit)]
                    except (IndexError, # List index out of range.
                            ValueError, # Invalid literal for int().
                            KeyError,   # Current is a dict without `int(bit)` key.
                            TypeError,  # Unsubscriptable object.
                            ):
                        # Missing attribute.
                        raise VariableDoesNotExist(_("Failed lookup for key [%s]"
                                                     " in %r") % (bit, current))
                except Exception, e:
                    current = ''

        return current
Parser.variable_symbol = Variable


class EndSymbol(Symbol):
    """
    This simply represents the end of the token list. Since its binding power
    is zero (the default) it will not bind to any other token, ending the parse.
    """
    name = "(==end==)"
Parser.end_symbol = EndSymbol


class InfixOperator(Symbol):
    """
    Infix operators lies between two tokens, such as the add operator in 'a + b'.
    """
    def led(self, left):
        self.first = left;
        self.second = self.parser.expression(self.left_binding_power)
        return self


class InfixROperator(Symbol):
    """
    InfixROperator is a right associative infix operator, used to implement
    short-circuiting logical operators.
    """
    def led(self, left):
        self.first = left;
        self.second = self.parser.expression(self.left_binding_power - 1)
        return self


class PrefixOperator(Symbol):
    """
    Prefix operators bind strongly to the token on its left and consumes it.
    """
    def nud(self):
        this.first = self.parser.expression(70)
        return self

    def right(self, context):
        """
        For consistency the right is overloaded so the visually right is also
        the right on the parsing order.
        """
        return self.first.resolve(context)


class OpenGroupingSymbol(Symbol):
    """
    Starts a parenthesized expression. All a parenthesizes group does is change
    the binding power temporarily, so that the subexpression inside of it can
    bind directly with other symbols. Since there is no need for it in the AST,
    it yields the subexpression, instead of itself.
    """
    name = "("
    # Has a super high binding power, so it can create a subexpression
    left_binding_power = 80

    def led(self, left):
        self.first = left
        self.second = self.parser.expression()
        self.parser.advance(')')
        return self

    def nud(self):
        expr = self.parser.expression()
        self.parser.advance(")")
        # Return the subexpression.
        return expr


class ClosingGroupingSymbol(Symbol):
    """
    Closes a parenthesized expression. Since it has no binding power the
    parsing algorithm stops when it gets to this.
    """
    name = ")"


def create_expression(exp):
    """
    Helper function. Returns an expression that can be evaluated.
    """
    lex = Lexer(exp)
    return Parser(lex).result()


