from reviewboard.policy.expression import create_expression
from reviewboard.policy.expression import InfixOperator, InfixROperator, PrefixOperator

# Arithmetic operators
class Plus(InfixOperator):
    name = "+"
    precedence = 50

    def resolve(self, context):
        return self.left(context) + self.right(context)


class Minus(InfixOperator):
    name = "-"
    precedence = 50

    def resolve(self, context):
        return self.left(context) - self.right(context)


class Times(InfixOperator):
    name = "*"
    precedence = 60

    def resolve(self, context):
        return self.left(context) * self.right(context)


class Divide(InfixOperator):
    name = "/"
    precedence = 60

    def resolve(self, context):
        return self.left(context) * self.right(context)


# Boolean operators
class And(InfixROperator):
    name = ('&&', 'and')
    precedence = 30

    def resolve(self, context):
        return self.left(context) and self.right(context)


class Or(InfixROperator):
    name = ('||', 'or')
    precedence = 30

    def resolve(self, context):
        return self.left(context) or self.right(context)


class In(InfixOperator):
    name = "in"
    precedence = 40

    def resolve(self, context):
        return self.left(context) in self.right(context)


class ComparisonOperators(InfixROperator):
    """
    An aggregator class for all boolean comparison operators of precedence 40.

    Demonstrates what can be done to group operators into fewer classes.
    """
    name = ("==", "is", "!=", "<", "<=", ">", ">=")
    precedence = 40

    mapping =  {
        "==": lambda x,y: x == y,
        "is": lambda x,y: x == y,
        "!=": lambda x,y: not x == y,
        "<" : lambda x,y: x < y,
        "<=": lambda x,y: x <= y,
        ">" : lambda x,y: x > y,
        ">=": lambda x,y: x >= y,
    }

    def resolve(self, context):
        return self.mapping[self.token](self.left(context), self.right(context))


class Not(PrefixOperator):
    name = "not"

    def resolve(self, context):
        return not self.right(context)


