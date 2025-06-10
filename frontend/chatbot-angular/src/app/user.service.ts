// src/app/user.service.ts

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import {catchError, firstValueFrom, map, Observable, of} from "rxjs";

@Injectable({
  providedIn: 'root',
})
export class UserService {
  private username: string = '';
  private apiUrl: string = 'http://localhost:5000';

  constructor(private http: HttpClient) {}

 setUsername(username: string): Observable<boolean> {
    console.log(`in service user set`)
  return this.http
    .post<{ success: boolean; message?: string }>(
      `${this.apiUrl}/set_username`,
      { username }
    )
    .pipe(
      map((response) => {
        if (response.success) {
          this.username = username;
          return true;
        } else {
          console.error(response.message || 'Failed to set username');
          return false;
        }
      }),
      catchError((error) => {
        console.error('An error occurred:', error);
        return of(false);
      })
    );
  }

  getUsername(): string {
    return this.username;
  }
}
