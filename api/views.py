# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from rest_framework import generics
from rest_framework import permissions
from rest_framework.views import APIView
from django.views.generic.base import TemplateView
from django.shortcuts import render
from django.template.loader import get_template
from django.http import HttpResponse
from django.contrib.auth.models import User
from rest_framework import status
from django.http import Http404
from django.contrib.auth import authenticate, login
from rest_framework.exceptions import ValidationError
from rest_framework import exceptions
from rest_framework_jwt.settings import api_settings
from rest_framework.test import APIClient
from rest_framework.response import Response
from .serializer import UserProfileSerializer, SkillSetSerializer
from .serializer import UserSerializer, ProjectSerializer, TeamSerializer, LoginSerializer, TokenSerializer
from .models import UserProfile, SkillSet, Project, Team, get_user_from_object
from api.utils.generate_jwt_token import generate_jwt_token
from api.utils.service import check_auth_user_credentials

# Create your views here.

jwt_payload_handler = api_settings.JWT_PAYLOAD_HANDLER
jwt_encode_handler = api_settings.JWT_ENCODE_HANDLER


class CreateUserView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """ create a user """
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            user_object = get_user_from_object(serializer.data['id'])
            token_serializer = TokenSerializer(data={
                "token": jwt_encode_handler(
                    jwt_payload_handler(user_object)
                )
                })
            if token_serializer.is_valid():
                response = {
                    'token': token_serializer.data['token'],
                    'id': serializer.data['id'],
                    'username': serializer.data['username'],
                    'first_name': serializer.data['first_name'],
                    'last_name': serializer.data['last_name'],
                    'email': serializer.data['email']
                }
                return Response(response, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """ Persist a username and password for authentication """
    permission_classes = [permissions.AllowAny]

    def validate_username_password(self, request, validated_data):
        email = validated_data.get('email')
        password = validated_data.get('password')

        if email and password:
            user = authenticate(request, username=email, password=password)
        else:
            msg = 'Must include a username and password to login'
            raise exceptions.ValidationError(msg)
        return user

    def post(self, request):
        """ Login a registered user """
        authenticated_user = self.validate_username_password(request, request.data)
        if authenticated_user is not None:
            serializer = LoginSerializer(authenticated_user)
            token_serializer = TokenSerializer(data={
                "token": jwt_encode_handler(
                    jwt_payload_handler(authenticated_user)
                )
            })
            if token_serializer.is_valid():
                response = {
                    'token':token_serializer.data,
                    'username': serializer.data['username'],
                    'first_name': serializer.data['first_name'],
                    'last_name': serializer.data['last_name'],
                    'email': serializer.data['email']
                }
                
                return Response(response, status=status.HTTP_200_OK)

        return Response(dict(error='Login failed'),status=status.HTTP_401_UNAUTHORIZED)


class CreateUserProfileView(generics.ListCreateAPIView):
    """ creates a userprofile for an authenticated user """
    permissions_classes = (permissions.IsAuthenticated,)
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer


class CreateSkillSetView(generics.ListCreateAPIView):
    """ creates a skillset for application """
    queryset = SkillSet.objects.all()
    serializer_class = SkillSetSerializer


class CreateProjectView(APIView):
    """ create a new project and get projects"""
    permissions_classes = (permissions.IsAuthenticated,)
    def existing_project(self, title):
        """ Helper function for checking if project exist """
        try:
            Project.objects.get(title=title)
            return True
        except Project.DoesNotExist:
            return False

    def get(self, request):
        """ Gets all projects """
        projects = Project.objects.all()
        serializer = ProjectSerializer(projects, many=True)
        return Response(serializer.data)

    def post(self, request):
        """ Creates a new project"""
        if not request.data['title']:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        existing_project = self.existing_project(request.data['title'])
        if not existing_project:
            serializer = ProjectSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_409_CONFLICT)


class CreateTeamView(APIView):
    """ creates a new team gets all teams """
    permissions_classes = (permissions.IsAuthenticated,)
    def existing_team(self, name):
        """ Helper function for checking if a team exist """
        try:
            Team.objects.get(name=name)
            return True
        except Team.DoesNotExist:
            return False

    def get(self, request):
        """ gets all teams """
        teams = Team.objects.all()
        serializer = TeamSerializer(teams, many=True)
        return Response(serializer.data)

    def post(self, request):
        """ creates a team """
        existing_team = self.existing_team(request.data['name'])

        if not existing_team:
            serializer = TeamSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_409_CONFLICT)


class UserProfileDetailsView(generics.RetrieveUpdateDestroyAPIView):
    """ updates,deletes and get the profile of an existing user """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer


class SkillSetDetailsView(generics.RetrieveUpdateDestroyAPIView):
    """ updates, deletes and get a particular skill with primary key """
    queryset = SkillSet.objects.all()
    serializer_class = SkillSetSerializer


class ProjectDetailsView(APIView):
    """ Retrieve, update and delete a project """
    permissions_classes = (permissions.IsAuthenticated,)
    def get_project_by_id(self, pk):
        """ Helper function to get project based on the primary key"""
        try:
            return Project.objects.get(pk=pk)
        except Project.DoesNotExist:
            raise Http404

    def get(self, request, pk, format=None):
        """ Gets a project """
        project = self.get_project_by_id(pk)
        credential_check = check_auth_user_credentials(request.user.id, project.author.id)
        if not credential_check:
            response_object = dict(message="You are not authorized to access the content")
            return Response(response_object, status=status.HTTP_403_FORBIDDEN)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = ProjectSerializer(project)
        return Response(serializer.data)

    def put(self, request, pk, format=None):
        """ Updates a project """
        
        project = self.get_project_by_id(pk)
        credential_check = check_auth_user_credentials(
            request.user.id, project.author.id
            )
        if not credential_check:
            response_object = dict(message="You are not authorized to access the content")
            return Response(response_object, status=status.HTTP_403_FORBIDDEN)
        serializer = ProjectSerializer(project, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        """ Deletes a project """
        project = self.get_project_by_id(pk=pk)
        credential_check = check_auth_user_credentials(
            request.user.id, project.author.id
        )
        if not credential_check:
            response_object = dict(message="You are not authorized to delete this content")
            return Response(response_object, status.HTTP_403_FORBIDDEN)
        if not project:
            return Response(status=status.HTTP_404_NOT_FOUND)
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TeamDetailsView(APIView):
    """ Retrieve, update, and delete a project """
    permissions_classes = (permissions.IsAuthenticated,)
    def get_team_by_id(self, pk):
        """ Helper function to get project based on the primary key"""
        try:
            return Team.objects.get(pk=pk)
        except Team.DoesNotExist:
            raise Http404

    def get(self, request, pk):
        """ gets a team by id """
        team = self.get_team_by_id(pk=pk)
        team_serializer = TeamSerializer(team)
        return Response(team_serializer.data)

    def put(self, request, pk):
        """ updates a team by id """
        team = self.get_team_by_id(pk=pk)
        team_serializer = TeamSerializer(team, data=request.data)
        if team_serializer.is_valid():
            team_serializer.save()
            return Response(team_serializer.data)
        return Response(team_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        """ delete a team by id """
        team = self.get_team_by_id(pk=pk)
        team.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
