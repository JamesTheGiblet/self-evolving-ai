package com.example.agents;

import com.example.agents.impl.ConcreteMetaAgent;
import com.example.agents.impl.ConcreteSkillAgent;
import com.example.agents.impl.ConcreteTaskAgent;
import com.example.agents.impl.ConcreteTaskRouter;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

public class FullSystemIntegrationTest {

    private MetaAgent metaAgent;
    private ConcreteTaskRouter taskRouter; // Keep a reference if needed for more complex setups

    @BeforeEach
    void setUp() {
        // Setup common to multiple tests can go here
        taskRouter = new ConcreteTaskRouter();

        // Setup Weather Agent and Skill
        SkillAgent weatherSkillAgent = new ConcreteSkillAgent("WeatherSkill");
        TaskAgent weatherTaskAgent = new ConcreteTaskAgent("WeatherTaskAgent");
        weatherTaskAgent.registerSkillAgent(weatherSkillAgent);
        taskRouter.registerTaskAgent("WeatherInquiry", weatherTaskAgent);

        // Setup Reminder Agent and Skill
        SkillAgent reminderSkillAgent = new ConcreteSkillAgent("ReminderSkill");
        TaskAgent reminderTaskAgent = new ConcreteTaskAgent("ReminderTaskAgent");
        reminderTaskAgent.registerSkillAgent(reminderSkillAgent);
        taskRouter.registerTaskAgent("SetReminder", reminderTaskAgent);

        metaAgent = new ConcreteMetaAgent(taskRouter);
    }

    @Test
    void testFullUserRequestFlow_WeatherInquiry_Successful() {
        // 1. Define Input
        String userInput = "WeatherInquiry:London";

        // 2. Execute Flow
        String response = metaAgent.processRequest(userInput);

        // 3. Assert Output
        String expectedResponse = "TaskAgent[WeatherTaskAgent] processed: SkillAgent[WeatherSkill] executed with: London";
        assertEquals(expectedResponse, response);
    }

    @Test
    void testFullUserRequestFlow_SetReminder_Successful() {
        String userInput = "SetReminder:Buy milk at 5 PM";
        String response = metaAgent.processRequest(userInput);
        String expectedResponse = "TaskAgent[ReminderTaskAgent] processed: SkillAgent[ReminderSkill] executed with: Buy milk at 5 PM";
        assertEquals(expectedResponse, response);
    }

    @Test
    void testFullUserRequestFlow_AgentNotFound() {
        String userInput = "UnknownTask:SomeData";
        String response = metaAgent.processRequest(userInput);
        assertEquals("Error: No agent found for request type 'UnknownTask'.", response);
    }

    @Test
    void testFullUserRequestFlow_InvalidRequestFormat() {
        // Test with input that doesn't match the "Type:Payload" structure
        String userInput = "JustSomeTextWithoutColon";
        String response = metaAgent.processRequest(userInput);
        // The current ConcreteMetaAgent splits by ":" and uses parts[0] as type.
        // If no colon, parts[0] is the whole string.
        assertEquals("Error: No agent found for request type 'JustSomeTextWithoutColon'.", response);
    }
}