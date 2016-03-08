'''Module contains definitions for model builder class.

A model builder's primary function is to generate python objects from a stream of token:value
pairs. These pairs will generally be the product of a pygments lexer.
'''

__author__ = 'erik'
# imports for base model
import pygments.token as Token
import collections
# imports for StateModelBuilder
import StateModel
from PlantUML_Lexer import STATE, SALIAS, SATTR, SSTART, SEND, TSOURCE, TDEST, TATTR

from Utilities.Logger import LogTools
dlog = LogTools('ModelBuilder.log', 'ModelBuilder')
dlog.rootlog.warning('Module initialized')


class ModelBuilder(object):

    # dictionary of {token types: callback functions}
    action_tokens = dict()

    # Text and Error tokens ignored by default
    ignored_tokens = [Token.Text, Token.Error]

    def __init__(self, model_class, *args, **kwargs):
        self.model_class = model_class
        self.model = self.model_class()

        self.q = collections.deque()  # holds tokens,val pairs drawn from the token generator
        # note: deque chosen over list because it's (1) thread-safe, (2) faster in size changes

    def parse(self, token_stream):
        '''Parses lexed data, executing callbck functions as defined in subclass token_dict
        :param: token_stream    token generator as generated by selected pygments lexer
        :returns: self.model_class instance
        '''
        actions_pending = 0

        for token_tup in token_stream:
            # filter out ignored_tokens defined at the class level
            # if token not part of actionable items, merely add it to the queue
            # otherwise take action on first actionable item in queue
            token = token_tup[0]
            if token in self.__class__.ignored_tokens:
                continue
            elif token in self.__class__.action_tokens:
                actions_pending += 1

            self.q.append(token_tup)

            if actions_pending > 1:
                if self.q[0][0] in self.action_tokens:
                    # execute function defined
                    self.action_tokens[self.q[0][0]]()
                    actions_pending -= 1
                else:
                    continue

        # finish processing any remaining actionable tokens
        # once the stream has dried up
        while actions_pending > 0:
            if self.q[0][0] in self.action_tokens:
                self.action_tokens[self.q[0][0]]()
                actions_pending -= 1
            else:
                dlog.rootlog.error("Non actionable token " + self.q.popleft() + " found at end of deque.")

        # deliver populated model
        return self.model


class StateModelBuilder(ModelBuilder):
    '''
    Generates State Models from a token stream.
    '''

    # dictionary used as case/switch statement
    action_tokens = {}

    def __init__(self, *args, **kwargs):

        ModelBuilder.__init__(self, StateModel.StateDiagram)

        # dictionary constructor - list of key,value pairs
        update_dict = dict( [
            (STATE, self.assign_state),
            (SALIAS, self.lookup_state),
            (SEND, self.end_superstate),
            (TSOURCE, self.assign_trans)
            ] )

        StateModelBuilder.action_tokens.update(update_dict)

        self.superstate_stack = [None]  # stack of nested superstates
        self.state_aliases = {}  # dictionary of {state_alias: state_name}
        self.diagram = self.model  # bind model instance to new name for code clarity

    def lookup_state(self):
        '''Will be implemented later'''
        raise NotImplementedError

    def assign_state(self):
        '''All state names are unique and required for assignment.
        Will not double-add states to self.diagram.'''
        state_name = self.q.popleft()[1]
        if self.q[0][0] == SSTART:
            self.start_superstate(state_name)
        else:
            self.diagram.add_state(state_name, parent_state=self.superstate_stack[-1])

        if self.q[0][0] == SATTR:
            self.add_state_attr(state_name, self.q.popleft()[1])

    def add_state_attr(self, state_name, attribute_value):
        self.diagram.add_state_attr(state_name, attribute_value)

    def start_superstate(self, state_name):
        self.q.popleft()[1]  # consume delimiter "{"
        self.diagram.add_state(state_name, parent_state=self.superstate_stack[-1])
        self.superstate_stack.append(state_name)

    def end_superstate(self):
        self.q.popleft()[1]  # consume delimiter "}"
        self.superstate_stack.pop(-1)

    def assign_trans(self):
        '''Assigns a transition to the diagram and State.source, State.destination values'''
        source = self.q.popleft()[1]
        # pull destination from token stream
        if self.q[0][0] == TDEST:
            dest = self.q.popleft()[1]
        else:
            dlog.rootlog.error("!ERROR: Transition source " + str(source) + " found without corresponding destination")
            raise AttributeError
        # add transition to graph
        if len(self.q) > 0 and self.q[0][0] == TATTR:
            transition_attribute = self.q.popleft()[1]
            self.diagram.add_transition(source, dest, parent_state=self.superstate_stack[-1],
                                        attributes=transition_attribute)
        else:
            self.diagram.add_transition(source, dest, parent_state=self.superstate_stack[-1])

def build_state_diagram(fpath):
    '''
    Returns a state diagram lexed from the given plantUML model
    :param fpath: path to state diagram *.puml file
    :return: StateModel.StateDiagram
    '''
    from PlantUML_Lexer import get_tokens_from_file

    tkns = get_tokens_from_file(fpath)
    builder = StateModelBuilder()
    diagram = builder.parse(tkns)

    dlog.rootlog.info("New diagram parsed from ", fpath)
    dlog.rootlog.info("Parsed " + str(len(diagram.state_names.values())) + "states")
    dlog.rootlog.info("Parsed " + str(len(diagram.get_transitions())) + "transitions")

    return diagram


if __name__ == "__main__":
    import config, os
    from PlantUML_Lexer import get_tokens_from_file

    config.sys_utils.set_pp_on()

    input_path = os.path.join(config.specs_path, 'vpeng', 'Demo_2.0.puml')

    tkns = get_tokens_from_file(input_path)

    builder = StateModelBuilder()
    diagram = builder.parse(tkns)

    print "Parsed", len(diagram.state_names.values()), "states"
    print "Parsed", len(diagram.get_transitions()), "transitions"

    print "=================== Testing Complete ==================="