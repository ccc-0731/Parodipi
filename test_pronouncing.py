import pronouncing

def count_syllables_in_word(word):
    phones = pronouncing.phones_for_word(word.lower())
    if not phones:
        return 1  # fallback guess
    return pronouncing.syllable_count(phones[0])

def count_syllables_in_sentence(sentence):
    return sum(count_syllables_in_word(w) 
               for w in sentence.split())

print(count_syllables_in_sentence("one point five"))