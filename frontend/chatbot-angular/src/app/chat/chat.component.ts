import { Component } from '@angular/core';
import {FormsModule} from '@angular/forms'
import { UserService } from '../user.service';
import { MessageService } from '../message.service';
import { io } from 'socket.io-client';
import {NgForOf, NgIf} from "@angular/common";
import markdownit from 'markdown-it';

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [FormsModule, NgForOf, NgIf],
  templateUrl: './chat.component.html',
  styleUrl: './chat.component.css'
})
export class ChatComponent {

    private socket = io('http://localhost:5000'); // Update with your server URL
    messages: { content: string; type: string }[] = [];
    input = '';
    isChatbotResponding = false;
    md = markdownit();

    constructor(
    private userService: UserService,
    private messageService: MessageService
  ) {}

    ngOnInit() {
      this.socket.on('response', (response: string) => {
        this.messages.push({ content: this.md.render(response), type: 'response' });
        this.isChatbotResponding = false;
      });
    }

    sendMessage() {
      // this.socket.emit('message', this.input);
      // this.messages.push({ content: this.md.render(`**You:** ${this.input}`), type: 'user' });
      // this.isChatbotResponding = true;
      // this.input = '';


      // Get the username from the user service
    const username = this.userService.getUsername();

    // Combine the username and message
    const fullMessage = this.md.render(`**${username}**: ${this.input}`);

    // Emit the combined message to the server
    this.socket.emit('message', this.input);

    // Add the combined message to the messages array
    this.messages.push({content: fullMessage, type: 'user'});

    // Indication of chatbot typing
    this.isChatbotResponding = true;

    // Save the message to the message service for future use
    this.messageService.addMessage(fullMessage);

    // Clear the input box
    this.input = '';
    }

    handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Enter') {
        this.sendMessage();
      }
    }

    exportChat() {
      const chatText = this.messages
        .map(message => (message.content || '').replace(/(\*\*You:\*\*)?/g, ''))
        .join('\n');

      const blob = new Blob([chatText], { type: 'text/plain' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'chat_history.txt';
      link.click();
    }

}
