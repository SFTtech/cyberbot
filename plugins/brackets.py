from matrix_bot_api.mregex_handler import MRegexHandler
import re

HELP_DESC = '(automatic)\t\tThe bot closes opened brackets without a counterpart'

def register_to(bot):

    BRACKET_SYNTAX = False
    """
    If this variable is set, syntactically correct closing of brackets is
    needed in order to prevent reporting by this plugin. If this variable is
    false, the plugin will simply print unclosed brackets, independent of
    placement.
    """

    def bracket_callback(room, event):
        brackets = {
            '(': ')', '[': ']', '{': '}', '<': '>',
            '„': '“',
            '“': '”', '‘': '’', '‹': '›', '«': '»',
            '（': '）', '［': '］', '｛': '｝', '｟': '｠',
            '⦅': '⦆', '〚': '〛', '⦃': '⦄',
            '「': '」', '〈': '〉', '《': '》', '【': '】', '〔': '〕', '⦗': '⦘',
            '『': '』', '〖': '〗', '〘': '〙',
            '⟦': '⟧', '⟨': '⟩', '⟪': '⟫', '⟮': '⟯', '⟬': '⟭', '⌈': '⌉',
            '⌊': '⌋', '⦇': '⦈', '⦉': '⦊',
            '❛': '❜', '❝': '❞', '❨': '❩', '❪': '❫', '❴': '❵', '❬': '❭',
            '❮': '❯', '❰': '❱',
            '❲': '❳', '﴾': '﴿',
            '〈': '〉', '⦑': '⦒', '⧼': '⧽',
            '﹙': '﹚', '﹛': '﹜', '﹝': '﹞',
            '⁽': '⁾', '₍': '₎',
            '⦋': '⦌', '⦍': '⦎', '⦏': '⦐', '⁅': '⁆',
            '⸢': '⸣', '⸤': '⸥',
        }
        rbrackets = { v : k for k, v in brackets.items() }  # reversed mapping

        smileys = [':-((', ':((', ':(', ':\'(', ':-(', '<3', '+o(', ':\'-(',
                   ';(', ';-(', '>.<', '>.>', '<.<' ':<', ':-<', '(:', ';)',
                   ';-)', '<--']

        result = []     # List of missing brackets, reported to chatroom
        stack = []      # Temporary stack of bracket counterparts
        message = event['content']['body']

        # Remove smileys from calculation
        for smiley in smileys:
            message = message.replace(smiley, '')

        # remove backticked source
        message = re.sub(r'```[^`]*```|`[^`]*`', '', string)

        # Process filtered message for possible missing closed brackets
        for character in message:
            char = brackets.get(character)

            if len(result) > 0:
                if (BRACKET_SYNTAX):
                    # Only allow syntactically correct bracket ordering
                    if character == result[-1]:
                        result.pop()
                        continue
                else:
                    # Return missing closed brackets, syntax correct or not
                    for r in result:
                        if (r == character):
                            result.remove(r)
                        break

            if char is not None:
                result.append(char)


        if len(result) > 0:
            result.reverse()
            room.send_text("".join(result))

        return False

    bracket_handler = MRegexHandler('', bracket_callback)
    bot.add_handler(bracket_handler)
