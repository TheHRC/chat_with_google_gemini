import { Component } from '@angular/core';
import {FormsModule} from "@angular/forms";
import {UserService} from "../user.service";
import {NgIf} from "@angular/common";

@Component({
  selector: 'app-user',
  standalone: true,
  imports: [
    FormsModule,
    NgIf
  ],
  templateUrl: './user.component.html',
  styleUrl: './user.component.css'
})
export class UserComponent {
  username: string = '';
  isVisible = true;

  constructor(private userService: UserService) {}

  setUsername(): void {
    if (this.username.trim() !== '') {
      console.log(`in user set user`)
      this.userService.setUsername(this.username);
      this.isVisible = false;
    }
  }
}
