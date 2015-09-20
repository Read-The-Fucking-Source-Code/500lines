"""A simple Python template renderer, for a nano-subset of Django syntax."""

# Coincidentally named the same as http://code.activestate.com/recipes/496702/

import re


class TempliteSyntaxError(ValueError):
    """Raised when a template has a syntax error."""
    pass


class CodeBuilder(object):
    """Build source code conveniently."""
    """生成 python 代码"""

    def __init__(self, indent=0):
        self.code = []
        # 用 [] 是不想使用 += 的方式拼接字符串
        self.indent_level = indent
        # 当前缩进

    def __str__(self):
        return "".join(str(c) for c in self.code)

    def add_line(self, line):
        """Add a line of source to the code.

        Indentation and newline will be added for you, don't provide them.

        增加一行语句

        """
        self.code.extend([" " * self.indent_level, line, "\n"])

    def add_section(self):
        """Add a section, a sub-CodeBuilder."""
        # 新增一个代码块
        section = CodeBuilder(self.indent_level)
        self.code.append(section)
        return section

    INDENT_STEP = 4      # PEP8 says so!
    # 缩进步长，一个缩进包含多少个空格

    def indent(self):
        """Increase the current indent for following lines."""
        # 缩进前进一步
        self.indent_level += self.INDENT_STEP

    def dedent(self):
        """Decrease the current indent for following lines."""
        # 缩进后退一步
        self.indent_level -= self.INDENT_STEP

    def get_globals(self):
        """Execute the code, and return a dict of globals it defines."""
        # 执行代码，返回包含执行结果的名字空间
        # A check that the caller really finished all the blocks they started.
        assert self.indent_level == 0
        # Get the Python source as a single string.
        python_source = str(self)
        # Execute the source, defining globals, and return them.
        global_namespace = {}
        exec(python_source, global_namespace)
        return global_namespace


class Templite(object):
    """A simple template renderer, for a nano-subset of Django syntax.

    Supported constructs are extended variable access::

        {{var.modifer.modifier|filter|filter}}

    loops::

        {% for var in list %}...{% endfor %}

    and ifs::

        {% if var %}...{% endif %}

    Comments are within curly-hash markers::

        {# This will be ignored #}

    Construct a Templite with the template text, then use `render` against a
    dictionary context to create a finished string::

        templite = Templite('''
            <h1>Hello {{name|upper}}!</h1>
            {% for topic in topics %}
                <p>You are interested in {{topic}}.</p>
            {% endif %}
            ''',
            {'upper': str.upper},
        )
        text = templite.render({
            'name': "Ned",
            'topics': ['Python', 'Geometry', 'Juggling'],
        })

    """
    # 解析模板字符串，渲染模板
    def __init__(self, text, *contexts):
        """Construct a Templite with the given `text`.

        `contexts` are dictionaries of values to use for future renderings.
        These are good for filters and global values.

        """
        self.context = {}
        for context in contexts:
            self.context.update(context)

        self.all_vars = set()
        self.loop_vars = set()

        # We construct a function in source form, then compile it and hold onto
        # it, and execute it to render the template.
        code = CodeBuilder()

        code.add_line("def render_function(context, do_dots):")
        # 生成的 python 代码都放在 render_function 函数中
        code.indent()
        vars_code = code.add_section()
        # 用于定义其他的变量，使用当前的缩进
        code.add_line("result = []")
        # 存最终结果
        code.add_line("append_result = result.append")
        code.add_line("extend_result = result.extend")
        code.add_line("to_str = str")
        # 性能优化

        buffered = []
        def flush_output():
            """Force `buffered` to the code builder."""
            # 把结果存到 result 里
            if len(buffered) == 1:
                code.add_line("append_result(%s)" % buffered[0])
            elif len(buffered) > 1:
                code.add_line("extend_result([%s])" % ", ".join(buffered))
            del buffered[:]

        ops_stack = []
        # 保存解析到的 token, 比如 if, for
        # 用于缩进后退以及判断是否忘了结束 token

        # Split the text to form a list of tokens.
        tokens = re.split(r"(?s)({{.*?}}|{%.*?%}|{#.*?#})", text)
        # 按 token 分割
        # 支持 {{ }}, {% %}, {# #}

        for token in tokens:
            if token.startswith('{#'):
                # Comment: ignore it and move on.
                # 注释
                continue
            elif token.startswith('{{'):
                # An expression to evaluate.
                # {{ foobar }}
                expr = self._expr_code(token[2:-2].strip())
                buffered.append("to_str(%s)" % expr)
            elif token.startswith('{%'):
                # Action tag: split into words and parse further.
                # 标签, if or for
                flush_output()
                words = token[2:-2].strip().split()
                if words[0] == 'if':
                    # An if statement: evaluate the expression to determine if.
                    # {% if expr %}
                    if len(words) != 2:
                        self._syntax_error("Don't understand if", token)
                    ops_stack.append('if')
                    code.add_line("if %s:" % self._expr_code(words[1]))
                    code.indent()
                elif words[0] == 'for':
                    # A loop: iterate over expression result.
                    # {% for expr in foobar %}
                    if len(words) != 4 or words[2] != 'in':
                        self._syntax_error("Don't understand for", token)
                    ops_stack.append('for')
                    self._variable(words[1], self.loop_vars)
                    # 存储循环表达式产生的变量
                    # {% for expr in foobar %} 中的 expr
                    code.add_line(
                        "for c_%s in %s:" % (
                            words[1],
                            self._expr_code(words[3])
                        )
                    )
                    code.indent()
                    # 缩进前进一步，进入 for 内部
                elif words[0].startswith('end'):
                    # Endsomething.  Pop the ops stack.
                    # {% endif %}, {% endfor %}
                    if len(words) != 1:
                        self._syntax_error("Don't understand end", token)
                    end_what = words[0][3:]
                    if not ops_stack:
                        self._syntax_error("Too many ends", token)
                    start_what = ops_stack.pop()
                    # tag 结束，把它对应的起始 tag 从 ops_stack 中移除
                    if start_what != end_what:
                        self._syntax_error("Mismatched end tag", end_what)
                    code.dedent()
                    # 缩进后退一步, if 或 for 结束
                else:
                    self._syntax_error("Don't understand tag", words[0])
            else:
                # Literal content.  If it isn't empty, output it.
                if token:
                    buffered.append(repr(token))

        if ops_stack:
            self._syntax_error("Unmatched action tag", ops_stack[-1])

        flush_output()

        for var_name in self.all_vars - self.loop_vars:
            vars_code.add_line("c_%s = context[%r]" % (var_name, var_name))

        code.add_line("return ''.join(result)")
        code.dedent()
        self._render_function = code.get_globals()['render_function']
        # 根据模板内容生成的 render_function 函数对象

    def _expr_code(self, expr):
        """Generate a Python expression for `expr`."""
        # 支持 {{ foo }}, {{ foo|bar }}, {{ foo.bar }}
        # 将局部变量替换为 c_ 开头的变量
        if "|" in expr:
            # 过滤器
            pipes = expr.split("|")
            code = self._expr_code(pipes[0])
            for func in pipes[1:]:
                self._variable(func, self.all_vars)
                code = "c_%s(%s)" % (func, code)
        elif "." in expr:
            # 通过 . 访问 属性, 方法，字典 key
            dots = expr.split(".")
            code = self._expr_code(dots[0])
            args = ", ".join(repr(d) for d in dots[1:])
            code = "do_dots(%s, %s)" % (code, args)
        else:
            self._variable(expr, self.all_vars)
            code = "c_%s" % expr
        return code

    def _syntax_error(self, msg, thing):
        """Raise a syntax error using `msg`, and showing `thing`."""
        raise TempliteSyntaxError("%s: %r" % (msg, thing))

    def _variable(self, name, vars_set):
        """Track that `name` is used as a variable.

        Adds the name to `vars_set`, a set of variable names.

        Raises an syntax error if `name` is not a valid name.

        保持模板中定义的变量名称

        """
        if not re.match(r"[_a-zA-Z][_a-zA-Z0-9]*$", name):
            self._syntax_error("Not a valid name", name)
        vars_set.add(name)

    def render(self, context=None):
        """Render this template by applying it to `context`.

        `context` is a dictionary of values to use in this rendering.

        """
        # Make the complete context we'll use.
        render_context = dict(self.context)
        # 复制一个 context 副本
        if context:
            render_context.update(context)
        return self._render_function(render_context, self._do_dots)
        # 调用生成的函数，得到最终渲染后的字符串

    def _do_dots(self, value, *dots):
        """Evaluate dotted expressions at runtime."""
        # 通过 . 访问 属性, 方法，字典 key
        for dot in dots:
            try:
                value = getattr(value, dot)
            except AttributeError:
                value = value[dot]
            if callable(value):
                value = value()
        return value
