import operator
import sys

from spec import Spec, skip, eq_, raises, assert_raises

from invoke.collection import Collection
from invoke.tasks import task, Task
from invoke.vendor import six
from invoke.vendor.six.moves import reduce

from _utils import load, support_path


@task
def _mytask():
    six.print_("woo!")

def _func():
    pass


class Collection_(Spec):
    class init:
        "__init__"
        def can_accept_task_varargs(self):
            "can accept tasks as *args"
            @task
            def task1():
                pass
            @task
            def task2():
                pass
            c = Collection(task1, task2)
            assert 'task1' in c
            assert 'task2' in c

        def can_accept_collections_as_varargs_too(self):
            sub = Collection('sub')
            ns = Collection(sub)
            eq_(ns.collections['sub'], sub)

        def kwargs_act_as_name_args_for_given_objects(self):
            sub = Collection()
            @task
            def task1():
                pass
            ns = Collection(loltask=task1, notsub=sub)
            eq_(ns['loltask'], task1)
            eq_(ns.collections['notsub'], sub)

        def initial_string_arg_acts_as_name(self):
            sub = Collection('sub')
            ns = Collection(sub)
            eq_(ns.collections['sub'], sub)

        def initial_string_arg_meshes_with_varargs_and_kwargs(self):
            # Collection('myname', atask, acollection, othertask=taskobj, ...)
            @task
            def task1():
                pass
            @task
            def task2():
                pass
            sub = Collection('sub')
            ns = Collection('root', task1, sub, sometask=task2)
            for x, y in (
                (ns.name, 'root'),
                (ns['task1'], task1),
                (ns.collections['sub'], sub),
                (ns['sometask'], task2),
            ):
                eq_(x, y)

    class from_module:
        def setup(self):
            self.c = Collection.from_module(load('integration'))

        class parameters:
            def setup(self):
                self.mod = load('integration')
                self.fm = Collection.from_module

            def name_override(self):
                eq_(self.fm(self.mod).name, 'integration')
                eq_(
                    self.fm(self.mod, name='not-integration').name,
                    'not-integration'
                )

            def inline_configuration(self):
                eq_(self.fm(self.mod).configuration(), {})
                eq_(
                    self.fm(self.mod, config={'foo': 'bar'}).configuration(),
                    {'foo': 'bar'}
                )

            def name_and_config_simultaneously(self):
                # Test w/ posargs to enforce ordering, just for safety.
                c = self.fm(self.mod, 'the name', {'the': 'config'})
                eq_(c.name, 'the name')
                eq_(c.configuration(), {'the': 'config'})

        def adds_tasks(self):
            assert 'print_foo' in self.c

        def derives_collection_name_from_module_name(self):
            eq_(self.c.name, 'integration')

        def submodule_names_are_stripped_to_last_chunk(self):
            with support_path():
                from package import module
            c = Collection.from_module(module)
            eq_(module.__name__, 'package.module')
            eq_(c.name, 'module')
            assert 'mytask' in c # Sanity

        def honors_explicit_collections(self):
            coll = Collection.from_module(load('explicit_root'))
            assert 'top_level' in coll.tasks
            assert 'sub' in coll.collections
            # The real key test
            assert 'sub_task' not in coll.tasks

        def allows_tasks_with_explicit_names_to_override_bound_name(self):
            coll = Collection.from_module(load('subcollection_task_name'))
            assert 'explicit_name' in coll.tasks # not 'implicit_name'

        def returns_unique_Collection_objects_for_same_input_module(self):
            # Ignoring self.c for now, just in case it changes later.
            # First, a module with no root NS
            mod = load('integration')
            c1 = Collection.from_module(mod)
            c2 = Collection.from_module(mod)
            assert c1 is not c2
            # Now one *with* a root NS (which was previously buggy)
            mod2 = load('explicit_root')
            c3 = Collection.from_module(mod2)
            c4 = Collection.from_module(mod2)
            assert c3 is not c4

        class explicit_root_ns:
            def setup(self):
                mod = load('explicit_root')
                mod.ns.configure({'key': 'builtin', 'otherkey': 'yup'})
                mod.ns.name = 'builtin_name'
                self.unchanged = Collection.from_module(mod)
                self.changed = Collection.from_module(
                    mod,
                    name='override_name',
                    config={'key': 'override'}
                )

            def inline_config_with_root_namespaces_overrides_builtin(self):
                eq_(self.unchanged.configuration()['key'], 'builtin')
                eq_(self.changed.configuration()['key'], 'override')

            def inline_config_overrides_via_merge_not_replacement(self):
                assert 'otherkey' in self.changed.configuration()

            def inline_name_overrides_root_namespace_object_name(self):
                eq_(self.unchanged.name, 'builtin_name')
                eq_(self.changed.name, 'override_name')

            def root_namespace_object_name_overrides_module_name(self):
                # Duplicates part of previous test for explicitness' sake.
                # I.e. proves that the name doesn't end up 'explicit_root'.
                eq_(self.unchanged.name, 'builtin_name')


    class add_task:
        def setup(self):
            self.c = Collection()

        def associates_given_callable_with_given_name(self):
            self.c.add_task(_mytask, 'foo')
            eq_(self.c['foo'], _mytask)

        def uses_function_name_as_implicit_name(self):
            self.c.add_task(_mytask)
            assert '_mytask' in self.c

        def prefers_name_kwarg_over_task_name_attr(self):
            self.c.add_task(Task(_func, name='notfunc'), name='yesfunc')
            assert 'yesfunc' in self.c
            assert 'notfunc' not in self.c

        def prefers_task_name_attr_over_function_name(self):
            self.c.add_task(Task(_func, name='notfunc'))
            assert 'notfunc' in self.c
            assert '_func' not in self.c

        @raises(ValueError)
        def raises_ValueError_if_no_name_found(self):
            # Can't use a lambda here as they are technically real functions.
            class Callable(object):
                def __call__(self):
                    pass
            self.c.add_task(Task(Callable()))

        @raises(ValueError)
        def raises_ValueError_on_multiple_defaults(self):
            t1 = Task(_func, default=True)
            t2 = Task(_func, default=True)
            self.c.add_task(t1, 'foo')
            self.c.add_task(t2, 'bar')

        @raises(ValueError)
        def raises_ValueError_if_task_added_mirrors_subcollection_name(self):
            self.c.add_collection(Collection('sub'))
            self.c.add_task(_mytask, 'sub')

        def allows_specifying_task_defaultness(self):
            self.c.add_task(_mytask, default=True)
            eq_(self.c.default, '_mytask')

        def specifying_default_False_overrides_task_setting(self):
            @task(default=True)
            def its_me():
                pass
            self.c.add_task(its_me, default=False)
            eq_(self.c.default, None)

    class add_collection:
        def setup(self):
            self.c = Collection()

        def adds_collection_as_subcollection_of_self(self):
            c2 = Collection('foo')
            self.c.add_collection(c2)
            assert 'foo' in self.c.collections

        def can_take_module_objects(self):
            self.c.add_collection(load('integration'))
            assert 'integration' in self.c.collections

        @raises(ValueError)
        def raises_ValueError_if_collection_without_name(self):
            # Aka non-root collections must either have an explicit name given
            # via kwarg, have a name attribute set, or be a module with
            # __name__ defined.
            root = Collection()
            sub = Collection()
            root.add_collection(sub)

        @raises(ValueError)
        def raises_ValueError_if_collection_named_same_as_task(self):
            self.c.add_task(_mytask, 'sub')
            self.c.add_collection(Collection('sub'))

    class getitem:
        "__getitem__"
        def setup(self):
            self.c = Collection()

        def finds_own_tasks_by_name(self):
            # TODO: duplicates an add_task test above, fix?
            self.c.add_task(_mytask, 'foo')
            eq_(self.c['foo'], _mytask)

        def finds_subcollection_tasks_by_dotted_name(self):
            sub = Collection('sub')
            sub.add_task(_mytask)
            self.c.add_collection(sub)
            eq_(self.c['sub._mytask'], _mytask)

        def honors_aliases_in_own_tasks(self):
            t = Task(_func, aliases=['bar'])
            self.c.add_task(t, 'foo')
            eq_(self.c['bar'], t)

        def honors_subcollection_task_aliases(self):
            self.c.add_collection(load('decorator'))
            assert 'decorator.bar' in self.c

        def honors_own_default_task_with_no_args(self):
            t = Task(_func, default=True)
            self.c.add_task(t)
            eq_(self.c[''], t)

        def honors_subcollection_default_tasks_on_subcollection_name(self):
            sub = Collection.from_module(load('decorator'))
            self.c.add_collection(sub)
            # Sanity
            assert self.c['decorator.biz'] is sub['biz']
            # Real test
            assert self.c['decorator'] is self.c['decorator.biz']

        @raises(ValueError)
        def raises_ValueError_for_no_name_and_no_default(self):
            self.c['']

        @raises(ValueError)
        def ValueError_for_empty_subcol_task_name_and_no_default(self):
            self.c.add_collection(Collection('whatever'))
            self.c['whatever']

    class to_contexts:
        def setup(self):
            @task
            def mytask(text, boolean=False, number=5):
                six.print_(text)
            @task(aliases=['mytask27'])
            def mytask2():
                pass
            @task(aliases=['othertask'], default=True)
            def subtask():
                pass
            sub = Collection('sub', subtask)
            self.c = Collection(mytask, mytask2, sub)
            self.contexts = self.c.to_contexts()
            alias_tups = [list(x.aliases) for x in self.contexts]
            self.aliases = reduce(operator.add, alias_tups, [])
            # Focus on 'mytask' as it has the more interesting sig
            self.context = [x for x in self.contexts if x.name == 'mytask'][0]

        def returns_iterable_of_Contexts_corresponding_to_tasks(self):
            eq_(self.context.name, 'mytask')
            eq_(len(self.contexts), 3)

        def allows_flaglike_access_via_flags(self):
            assert '--text' in self.context.flags

        def positional_arglist_preserves_order_given(self):
            @task(positional=('second', 'first'))
            def mytask(first, second, third):
                pass
            c = Collection()
            c.add_task(mytask)
            ctx = c.to_contexts()[0]
            eq_(ctx.positional_args, [ctx.args['second'], ctx.args['first']])

        def exposes_namespaced_task_names(self):
            assert 'sub.subtask' in [x.name for x in self.contexts]

        def exposes_namespaced_task_aliases(self):
            assert 'sub.othertask' in self.aliases

        def exposes_subcollection_default_tasks(self):
            assert 'sub' in self.aliases

        def exposes_aliases(self):
            assert 'mytask27' in self.aliases

    class task_names:
        def setup(self):
            self.c = Collection.from_module(load('explicit_root'))

        def returns_all_task_names_including_subtasks(self):
            eq_(set(self.c.task_names.keys()), set(['top_level', 'sub.sub_task']))

        def includes_aliases_and_defaults_as_values(self):
            names = self.c.task_names
            eq_(names['top_level'], ['othertop'])
            eq_(names['sub.sub_task'], ['sub.othersub', 'sub'])

    class configuration:
        "Configuration methods"
        def setup(self):
            self.c = Collection()

        def basic_set_and_get(self):
            self.c.configure({'foo': 'bar'})
            eq_(self.c.configuration(), {'foo': 'bar'})

        def configure_performs_merging(self):
            self.c.configure({'foo': 'bar'})
            eq_(self.c.configuration()['foo'], 'bar')
            self.c.configure({'biz': 'baz'})
            eq_(set(self.c.configuration().keys()), set(['foo', 'biz']))

        def configure_allows_overwriting(self):
            self.c.configure({'foo': 'one'})
            eq_(self.c.configuration()['foo'], 'one')
            self.c.configure({'foo': 'two'})
            eq_(self.c.configuration()['foo'], 'two')

        def call_returns_dict(self):
            eq_(self.c.configuration(), {})
            self.c.configure({'foo': 'bar'})
            eq_(self.c.configuration(), {'foo': 'bar'})

        def access_merges_from_subcollections(self):
            inner = Collection('inner')
            inner.configure({'foo': 'bar'})
            outer = Collection()
            outer.configure({'biz': 'baz'})
            # With no inner collection
            eq_(set(outer.configuration().keys()), set(['biz']))
            # With inner collection
            outer.add_collection(inner)
            eq_(set(outer.configuration('inner').keys()), set(['foo', 'biz']))

        def parents_overwrite_children_in_path(self):
            inner = Collection('inner')
            inner.configure({'foo': 'inner'})
            outer = Collection()
            outer.add_collection(inner)
            eq_(outer.configuration('inner')['foo'], 'inner')
            outer.configure({'foo': 'outer'})
            eq_(outer.configuration('inner')['foo'], 'outer')

        def sibling_subcollections_ignored(self):
            inner = Collection('inner')
            inner.configure({'foo': 'hi there'})
            inner2 = Collection('inner2')
            inner2.configure({'foo': 'nope'})
            outer = Collection(inner, inner2)
            eq_(outer.configuration('inner')['foo'], 'hi there')
            eq_(outer.configuration('inner2')['foo'], 'nope')

        def subcollection_paths_may_be_dotted(self):
            leaf = Collection('leaf')
            leaf.configure({'key': 'leaf-value'})
            middle = Collection('middle', leaf)
            outer = Collection('outer', middle)
            eq_(outer.configuration('middle.leaf'), {'key': 'leaf-value'})

        def invalid_subcollection_paths_result_in_KeyError(self):
            # Straight up invalid
            assert_raises(KeyError, Collection('meh').configuration, 'nope')
            # Exists but wrong level
            inner = Collection('inner')
            inner.configure({'foo': 'bar'})
            assert_raises(KeyError,
                Collection('outer', inner).configuration, 'foo')

        def keys_dont_have_to_exist_in_full_path(self):
            # Kinda duplicates earlier stuff; meh
            # Key only stored on leaf
            leaf = Collection('leaf')
            leaf.configure({'key': 'leaf-value'})
            middle = Collection('middle', leaf)
            outer = Collection('outer', middle)
            eq_(outer.configuration('middle.leaf'), {'key': 'leaf-value'})
            # Key stored on mid + leaf but not outer
            middle.configure({'key': 'whoa'})
            eq_(outer.configuration('middle.leaf'), {'key': 'whoa'})
