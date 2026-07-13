@bdd
Feature: Colon definitions
  As someone defining new Forth words
  I want to compose existing words into a colon definition
  So I can build higher-level words out of primitives

  Scenario: Defining SQUARE out of DUP and *
    Given a colon definition "SQUARE" made of the words "DUP *"
    When I push 3 and run "SQUARE"
    Then the top of the data stack is 9

  Scenario: A colon definition referencing an unknown word fails
    Given a colon definition "BROKEN" made of the words "NOT-A-WORD"
    When I try to run "BROKEN"
    Then it fails because the word was not found
