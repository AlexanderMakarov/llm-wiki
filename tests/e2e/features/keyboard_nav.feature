Feature: Keyboard navigation shortcuts
  As a visitor who prefers the keyboard
  I want `g h`, `g p`, `g s`, `/`, `?`, and `Escape` to work everywhere
  So I never need to reach for the mouse

  Background:
    Given a built llmwiki site on disk
    And I visit the homepage

  Scenario: "g h" jumps to home
    When I press "g" then "h"
    Then the URL path ends with "index.html" or "/"

  Scenario: "g p" jumps to projects
    When I press "g" then "p"
    Then the URL path contains "projects/index.html"

  Scenario: "g s" jumps to sessions
    When I press "g" then "s"
    Then the URL path contains "sessions/index.html"

  Scenario: "?" opens the help dialog
    When I press "?"
    Then the help dialog becomes visible

  Scenario: "/" opens the command palette
    When I press "/"
    Then the command palette becomes visible

  Scenario: Escape closes the command palette
    When I press "/"
    And the command palette becomes visible
    And I press "Escape"
    Then the command palette becomes hidden

  Scenario: Escape closes the help dialog
    When I press "?"
    And the help dialog becomes visible
    And I press "Escape"
    Then the help dialog becomes hidden

  Scenario: "g" alone without a second key does nothing destructive
    When I press "g"
    And I wait 1500 milliseconds
    Then the URL path ends with "index.html" or "/"

  Scenario: Typing in the palette input does not trigger shortcuts
    When I press "/"
    And the command palette becomes visible
    And I type "hello" into the palette input
    Then the palette input is focused
