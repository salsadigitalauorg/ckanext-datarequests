@users
Feature: Organization APIs

    @unauthenticated
    Scenario: Organisation overview is accessible to everyone
        Given "Unauthenticated" as the persona
        When I go to organisation page
        Then I should see "Test Organisation"
        And I should not see an element with xpath "//a[contains(@href, '?action=read')]"
        And I should see an element with xpath "//a[contains(@href, '/organization/test-organisation')]"
        When I press "Test Organisation"
        And I press "Activity Stream"
        Then I should see "created the organization"

        When I view the "test-organisation" organisation API "not including" users
        Then I should see an element with xpath "//*[contains(string(), '"success": true') and contains(string(), '"name": "test-organisation"')]"

