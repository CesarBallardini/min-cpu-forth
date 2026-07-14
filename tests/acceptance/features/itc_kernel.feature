@bdd
Feature: Threaded execution of colon definitions
  As someone building a Forth kernel
  I want colon definitions to run as real Indirect Threaded Code
  So that words execute through NEXT/DOCOL/EXIT over a dictionary in memory

  Scenario: Running a colon definition as threaded code
    Given a threaded colon definition "SQUARE" of "DUP *"
    When I boot the kernel with "LIT 3 SQUARE BYE"
    Then the threaded data stack top is 9

  Scenario: Nested colon definitions
    Given a threaded colon definition "SQUARE" of "DUP *"
    And a threaded colon definition "FOURTH" of "SQUARE SQUARE"
    When I boot the kernel with "LIT 2 FOURTH BYE"
    Then the threaded data stack top is 16

  Scenario: Multiplying two literals directly
    When I boot the kernel with "LIT 5 LIT 3 * BYE"
    Then the threaded data stack top is 15

  Scenario: A colon definition of stack and arithmetic primitives
    Given a threaded colon definition "DIFF" of "SWAP -"
    When I boot the kernel with "LIT 3 LIT 10 DIFF BYE"
    Then the threaded data stack top is 7

  Scenario: A comparison word pushes a flag
    When I boot the kernel with "LIT 4 LIT 4 = BYE"
    Then the threaded data stack top is 1
